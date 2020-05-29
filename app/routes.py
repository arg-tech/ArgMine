from flask import render_template, request, redirect, session, Markup
from . import application
import pandas as pd
from urllib.request import urlopen
import requests
import json
import urllib
import tempfile
import os
import uuid
import nltk
from nltk.tokenize import sent_tokenize
from joblib import load
from app.centrality import Centrality
from app.SentenceSimilarity import SentenceSimilarity
from fuzzywuzzy import fuzz
import spacy
from copy import deepcopy
import glob
import ast




@application.route('/')
@application.route('/index')
def index():
    return redirect('/home')
@application.route('/home')
def home_render():
    return render_template('home.html')

@application.route('/home', methods=['POST'])
def index_post():
    aif_mode = 'false'
    han_mode = 'false'
    ex_aif_mode = 'false'
    external_text = request.form['edata']
    source_text = request.form['sdata']
    aif_mode = request.form['aif_mode']
    ex_aif_mode = request.form['ex_aif_mode']
    han_mode = request.form['han_mode']
    session['s_text'] = source_text
    session['e_text'] = external_text
    session['aif'] = aif_mode
    session['han'] = han_mode
    session['e_aif'] = ex_aif_mode

    return redirect('/results')


@application.route('/results')
def render_text():
    source_text = session.get('s_text', None)
    external_text = session.get('e_text', None)
    aif_mode = session.get('aif', None)
    han_mode = session.get('han', None)
    ex_aif_mode = session.get('e_aif', None)
    centra = Centrality()
    print(aif_mode, han_mode, ex_aif_mode)
    if aif_mode == "true" and han_mode == "true" and ex_aif_mode == "false":
        # Source Map and Hansard
        print(source_text)


    elif aif_mode == "true" and han_mode == "false" and ex_aif_mode == "true":
        # Source Map and External Map
        print(source_text)
        print(external_text)
    elif aif_mode == "false" and han_mode == "true" and ex_aif_mode == "false":
        # Source Text and Hansard
        print('Getting AMF CAlls')
        s_map_numbers = do_amf_calls(source_text, False)
        print(s_map_numbers)
        central_nodes = centra.get_top_nodes_combined(s_map_numbers)

        source_topic_text = get_topic_text(central_nodes)
        txt_df = sent_to_df(source_topic_text)
        result = predict_topic(txt_df)
        print(source_topic_text, result)
        print('Got Hansard Topic')
        print(central_nodes)
        hansard_fp = get_hansard_file_path('2020-05-24', result, 'HansardDataAMF')
        hansard_map_num = check_hansard_path(hansard_fp)
        print(hansard_map_num)
        if hansard_map_num[0] == '':
            hansard_text = get_hansard_text(hansard_fp)
            hansard_text = hansard_text.decode("utf-8")
            print('Calling Hansard AMF calls')
            h_map_numbers = do_amf_calls(hansard_text, True)
            write_to_csv(h_map_numbers, hansard_fp)
        else:
            print('Gettting previous Hansard Map')
            h_map_numbers = hansard_map_num

            h_map_numbers = ast.literal_eval(h_map_numbers)

        h_i_nodes = centra.get_all_nodes_combined(h_map_numbers)

        #print(central_nodes, h_i_nodes)

        relations = itc_matrix(central_nodes, h_i_nodes)
        if len(relations > 0):
            #Build itc map
            build_itc_map(relations)





    elif aif_mode == "false" and han_mode == "false" and ex_aif_mode == "false":
        # Source Text and External Text
        print(source_text)
        print(external_text)
    elif aif_mode == "false" and han_mode == "false" and ex_aif_mode == "true":
        # Source Text and External Map
        print(external_text)





    a = 'A jewel is a precious stone used to decorate valuable things that you wear, such as rings or necklaces.'
    b = 'A gem is a jewel or stone that is used in jewellery.'
    parsed_text = get_parsed_text(a)
    similarity = get_similarity(a, b)
    if similarity > 1 or similarity == 0:
        similarity = get_fuzzy_similarity(a, b)



    return render_template('results.html', source_text=source_text)

def sent_to_df(txt):
    txt_pred = {'text': [txt]}
    df = pd.DataFrame(data=txt_pred)
    return df

def predict_topic(df):
    model_path = 'static/model/final_hansard_topic_model_seed.joblib'
    with application.open_resource(model_path) as load_m:
        loaded_m = load(load_m)
    pred = loaded_m.predict(df['text'])
    result = pred[0]
    return result

def get_hansard_file_path(input_date, topic, han_directory):
    files_list = []
    for subdir, dirs, files in os.walk(os.path.join(application.static_folder, han_directory)):
        for file_name in files:
            if 'txt' in file_name:
                full_path = subdir + '/' + file_name
                date = subdir.split(os.path.sep)[1]
                date = date.replace("-","")
                file = str(file_name).lower()
                file_tup = (full_path, date, file)
                files_list.append(file_tup)

    sorted_files = sorted(files_list, key=lambda tup: tup[1], reverse=True)
    input_date = input_date.replace('-', '')
    selected_file = ''
    for tup in sorted_files:
        date = tup[1]
        file_name = tup[2]
        file_path = tup[0]
        if input_date < date:
            continue
        else:
            if topic in file_name:
                selected_file = file_path

    if selected_file == '':
        for tup in sorted_files:
            date = tup[1]
            file_name = tup[2]
            file_path = tup[0]
            if topic in file_name:
                selected_file = file_path

    if not selected_file == '':
        selected_file = selected_file.split('/app/')[1]
    return selected_file

def get_hansard_text(file_path):

    with application.open_resource(file_path) as text_file:
        text = text_file.read()
    #text = text.encode('utf-8')
    return text

def text_to_lines(textData):
    fin_list = []
    lines_speakers = textData.splitlines(keepends=True)
    for line in lines_speakers:
        sentence_list = sent_tokenize(line)
        if len(sentence_list) > 0 and len(sentence_list) < 2:
            sent = sentence_list[0]
            if len(sent) > 0:
                fin_list.append(line)
        elif len(sentence_list) > 0:
            fin_list.append(line)

    return fin_list

def chunk_words(text_list):
    word_counter = 0
    chunks = []
    temp_list = []
    word_count_flag = False
    for line in text_list:
        words = line.split()
        word_counter += len(words)
        if word_counter > 700:
            word_counter = len(words)
            chunks.append(deepcopy(temp_list))
            temp_list = []
            word_count_flag = True
        temp_list.append(line)
    if word_counter < 700:
        chunks.append(deepcopy(temp_list))
    return chunks

def aif_upload(url, aif_data):
    aif_data = str(aif_data)
    filename = uuid.uuid4().hex
    filename = filename + '.json'
    with open(filename,"w") as fo:
        fo.write(aif_data)
    files = {
        'file': (filename, open(filename, 'rb')),
    }
    #get corpus ID

    aif_response = requests.post(url, files=files, auth=('test', 'pass'))
    #change this to pass the response back as text rather than as the full JSON output, this way we either pass back that a corpus was added to or a map uplaoded with map ID. Might be worth passing MAPID and Corpus name back in that situation.

    os.remove(filename)
    return aif_response.text

def post_turns(url,text_str):
    text_str = str(text_str)
    filename = uuid.uuid4().hex
    filename = filename + '.txt'
    with open(filename,"w") as fo:
        fo.write(text_str)
    files = {
        'file': (filename, open(filename, 'rb')),
    }
    #get corpus ID
    response = requests.post(url, files=files)
    os.remove(filename)
    return response

def post(url,text_str):
    #print(text_str)
    #text_str = str(text_str)
    filename = uuid.uuid4().hex
    filename = filename + '.txt'
    with open(filename,"w") as fo:
        fo.write(text_str)
    files = {
        'file': (filename, open(filename, 'rb')),
    }
    #get corpus ID

    response = requests.post(url, files=files)
    os.remove(filename)
    return response

def call_amf(chunks, test_flag):
    map_nums = []
    url_turn = 'http://turninator.arg.tech/turninator'
    url_props = 'http://propositionalizer.arg.tech/propositionalizer'
    url_aif = 'http://www.aifdb.org/json/'
    #URL for hosting outwith ARG-Tech Infrastrucutre
    url_inf = 'http://dam-02.arg.tech/dam-02'
    #url_inf = 'http://cicero.arg.tech:8092/dam-02'
    for i, chunk in enumerate(chunks):
        #print('######################################################')
        #print('Processing chunk ' + str(i) + ' of ' + str(len(chunks)))
        out_str = " ".join(chunk)
        out_str = out_str.replace('’', '')
        out_str = out_str.replace('‘', '')
        out_str = out_str.replace(',', '')
        out_str = out_str.replace('–', '')
        out_str = out_str.replace(')', '')
        out_str = out_str.replace('(', '')
        out_str = out_str.replace("/", '')
    #out_str = repr(out_str)
        word_count = len(out_str.split())
        #print(word_count)
    #print(out_str)
        #print('Getting Turns from AMF')
        prop_text_resp = post_turns(url_turn, out_str)
        prop_text = prop_text_resp.text
    #print(prop_text)
    #print(prop_text_resp)
        if prop_text == '':
        #print(prop_text)
            print('EMPTY return TURNS')
    #print(prop_text)
        #print('Getting Propositions from AMF')
        inf_text_resp = post(url_props, prop_text)
        inf_text = inf_text_resp.text
    #print(inf_text)
        if inf_text == '':
            print('EMPTY return PROPS')
        #break
        #print('Getting Inference relations from AMF')
        aif_json_resp = post(url_inf, inf_text)
        aif_json = aif_json_resp.text
    #print(aif_json)
        if aif_json == '':
            print('EMPTY return INF')
        #break
        #print('Uploading AIF to AIFdb')
    #print(aif_json)


    #Commented out so as to not ruin AIFdb

        map_response = aif_upload(url_aif, aif_json)
        map_data = json.loads(map_response)
        map_id = map_data['nodeSetID']
        map_nums.append(map_id)
        #print('Got nodeset ' + str(map_id) )
    #if test_flag:
    #    map_nums = [10670, 10671]
    #else:
    #    map_nums = [10672]
    print(map_nums)
    return map_nums


def get_similarity(sent1, sent2):
    sent_sim = SentenceSimilarity()
    similarity = sent_sim.main(sent1, sent2)
    return similarity

def get_fuzzy_similarity(sent1, sent2):
    sim = fuzz.token_set_ratio(sent1,sent2)
    if sim == 0:
        return 0
    else:
        return sim/100
def get_alternate_wn_similarity(sent1, sent2):
    sent_sim = SentenceSimilarity()
    similarity = sent_sim.symmetric_sentence_similarity(sent1, sent2)
    return similarity

def check_sim_thresholds(similarity, premise):
    negation_list = ['no', 'not', 'none', 'no one', 'nobody', 'nothing', 'neither', 'nowhere', 'never', 'hardly', 'scarcely', 'barely', 'doesnt', 'isnt', 'wasnt', 'shouldnt', 'wouldnt', 'couldnt', 'wont', 'cant', 'dont']
    if similarity > 0.8:
        return 'MA'
    if similarity > 0.6:
        negation_flag = False
        for neg in negation_list:
            premise = premise.lower()
            premise = premise.replace("'","")
            if neg in premise:
                negation_flag = True

        if negation_flag:
            return 'CA'
        else:
            return 'RA'
    else:
        return ''
def get_parsed_text(txt):
    pos_tok_list = ['SYM', 'DET', 'ADP', 'PUNCT', 'AUX', 'PART', 'SCONJ', 'X', 'CONJ']
    txt = process_text(txt)
    nlp = spacy.load("en")
    orig_doc = nlp(txt)
    sent = []
    sent_remove = []
    for token in orig_doc:
        pos_tok = token.pos_
        if 'PROPN' in pos_tok:
            sent.append('it')
        else:
            sent.append(token.text)
        if pos_tok in pos_tok_list:
            sent_remove.append(token.text)

    new_txt = ' '.join(sent)
    words = []
    doc = nlp(new_txt)
    for chunk in doc.noun_chunks:
        if 'nsubj' in chunk.root.dep_ or 'dobj' in chunk.root.dep_ or 'pobj' in chunk.root.dep_ or 'nmod' in chunk.root.dep_ or 'obl' in chunk.root.dep_:
            words.append(chunk.text)
            words.append(chunk.root.head.text)
    words = [i.strip() for i in words]
    res = list(set(words)^set(sent_remove))
    a = set(res)
    new_res = list(a)
    parsed_text = ' '.join(new_res)
    parsed_text = parsed_text.replace(".", "")
    parsed_text = parsed_text.replace(",", "")
    return parsed_text

def process_text(txt):
    txt = txt.lower()

    if 'but' in txt:
        txt = txt.split('but')[0]
    # and? .? ,? because?
    return txt

def get_topic_text(central_nodes_tup_list):
    overall_text = ''
    for tup in central_nodes_tup_list:
        txt = tup[1]
        parsed_text = get_parsed_text(txt)
        overall_text = overall_text + parsed_text + ' '
    return overall_text

def do_amf_calls(s_txt, test_flag):
    s_txt_lst = text_to_lines(s_txt)
    removetable = str.maketrans('', '', '@#%-;')
    out_list = [s.translate(removetable) for s in s_txt_lst]
    chunks = chunk_words(out_list)
    print('Calling AMF')
    s_map_numbers = call_amf(chunks, test_flag)
    return s_map_numbers

def itc_matrix(source_nodes, other_nodes):
    relations = []
    print(other_nodes)
    for node in source_nodes:
        node_id = node[0]
        node_text = node[1]


        for ex_nodes in other_nodes:
            ex_id = ex_nodes[0]
            ex_text = ex_nodes[1]

            print('COMPARING: ')
            print(node_text, ex_text)
            #node_parsed_text = get_parsed_text(node_text)
            #ex_parsed_text = get_parsed_text(ex_text)
            if ex_text == '' or node_text == '':
                continue
            else:
                similarity = get_similarity(node_text, ex_text)
                if similarity > 1 or similarity == 0:
                    #similarity = get_fuzzy_similarity(node_parsed_text, ex_parsed_text)
                    similarity = get_alternate_wn_similarity(node_text, ex_text)


                relation = check_sim_thresholds(similarity, ex_text)
                if relation == '':
                    continue
                else:
                    relation_tup = (node_id, node_text, ex_id, ex_text, relation)
                    relations.append(relation_tup)

    return relations


def check_hansard_path(hansard_fp):
    file_name = 'hansard_maps.csv'

    files_present = glob.glob(file_name)

    if not files_present:
        return ['']
    else:
        hansard_df = pd.read_csv(file_name)

        sel_df = hansard_df[hansard_df['filename'] == hansard_fp]
        if len(sel_df) < 1:
            return ['']
        else:
            sel_df.reset_index(inplace=True)
            return sel_df['map_id'][0]
def write_to_csv(map_numbers, hansard_fp):
    file_name = 'hansard_maps.csv'

    files_present = glob.glob(file_name)

    if not files_present:
        #create df and write
        df = pd.DataFrame({'filename': hansard_fp, 'map_id': [map_numbers]})
        df.to_csv(file_name)
    else:
        df = pd.DataFrame({'filename': hansard_fp, 'map_id': [map_numbers]})
        df.to_csv(file_name, mode='a', header=False)
        #create df and write
def build_itc_map(relations):
    return ''




