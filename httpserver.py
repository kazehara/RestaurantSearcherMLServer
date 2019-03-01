# -*- coding: utf-8 -*-
from bottle import route, run, request, HTTPResponse, hook, response

from rsearcher.analyst import Analyst
from rsearcher.query import QueryParser
from rsearcher.word2vec import Word2VecModel
from elastic import ElasticModel
from dbmodel import DBModel

import json
import numpy as np


candidates = []
choice_bodies = []
top = 0


def get_reply(query):
    global candidates, choice_bodies, top

    candidates = []
    choice_bodies = []
    top = 0

    parser.drop_morph(query)

    word_pairs = word2vec_model.similar_words(parser.words)
    word_pairs = word2vec_model.most_significant_word_pairs(word_pairs)

    terms = [word for word, _ in word_pairs]

    elastic_results = elastic_model.search_terms(terms)

    bodies = elastic_results[0]

    analyst = Analyst(word2vec_model, specific_parts=['普通名詞', '地名', '固有名詞', '組織名'])

    all_sum_scores = []
    all_scores = []
    all_candidates = []

    for body in elastic_results[0]:
        analyst.parse(body['_source']['body'])
        candidate_scores = np.array(analyst.calc_candidate_score())
        query_base_scores = np.array(analyst.calc_query_base_score(parser.words))
        scores = list(candidate_scores + query_base_scores)

        all_sum_scores.append(sum(scores) / (len(scores) if len(scores) != 0 else 1))
        all_scores.append(scores)
        all_candidates.append(analyst.candidates)

    indices = np.argsort(all_sum_scores)[::-1]

    for index in indices:
        choice_bodies.append(bodies[index])
        candidates_ = analyst.most_significant_candidates(
            all_scores[index],
            all_candidates[index]
        )
        candidates.append(candidates_)

    restaurant_db = DBModel('gourmet', 'localhost', 'foo', 'bar')
    name_result = restaurant_db.select('SELECT name FROM restaurants WHERE id={};'.format(
        choice_bodies[top]['_source']['restaurant_id']
    ))
    address_result = restaurant_db.select(
        'SELECT address FROM restaurants WHERE id={}'.format(
            choice_bodies[top]['_source']['restaurant_id']
        )
    )

    restaurant = 'こちらのお店はいかがでしょうか？\n\n店名 : {}'.format(name_result[0])
    if address_result[0] != 'nan':
        restaurant += '\n住所 : {}'.format(address_result[0])

    if len(candidates[top]) == 0 or candidates[top] is None:
        recommend = 'このお店に行ったことがある人は，残念ながら見つかりませんでした．'
    else:
        recommend = 'このお店に行った人は次のような感想を述べています :'
        for candidate in candidates[top]:
            recommend += '\n\n・{}'.format(candidate)

    dicts = [
        {'restaurant': restaurant, 'recommend': recommend}
    ]

    return json.dumps(dicts, ensure_ascii=False)


@hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'


@route('/talk', method='POST')
def talk():
    user_input = request.forms.user_input
    body = get_reply(user_input)
    r = HTTPResponse(status=200, body=body)
    r.set_header('Content-Type', 'application/json')
    r.set_header('Access-Control-Allow-Origin', '*')
    return r


@route('/retry', method='GET')
def retry():
    global choice_bodies, candidates, top

    top += 1
    if top + 1 >= len(candidates):
        r = HTTPResponse(status=500)
        r.set_header('Content-Type', 'application/json')
        r.set_header('Access-Control-Allow-Origin', '*')
        return r

    restaurant_db = DBModel('gourmet', 'localhost', 'foo', 'bar')
    name_result = restaurant_db.select('SELECT name FROM restaurants WHERE id={}'.format(
        choice_bodies[top]['_source']['restaurant_id']
    ))
    address_result = restaurant_db.select(
        'SELECT address FROM restaurants WHERE id={}'.format(
            choice_bodies[top]['_source']['restaurant_id']
        )
    )

    restaurant = 'こちらのお店はいかがでしょうか？\n\n店名 : {}'.format(name_result[0])
    if address_result[0] != 'nan':
        restaurant += '\n住所 : {}'.format(address_result[0])

    if len(candidates[top]) == 0 or candidates[top] is None:
        recommend = 'このお店に行ったことがある人は，残念ながら見つかりませんでした．'
    else:
        recommend = 'このお店に行ったことがある人は次のような感想を述べています :'
        for candidate in candidates[top]:
            recommend += '\n\n・{}'.format(candidate)

    dicts = [
        {'restaurant': restaurant, 'recommend': recommend}
    ]

    r = HTTPResponse(status=200, body=json.dumps(dicts, ensure_ascii=False))
    r.set_header('Content-Type', 'application/json')
    r.set_header('Access-Control-Allow-Origin', '*')
    return r


if __name__ == '__main__':
    parser = QueryParser(specific_parts=['普通名詞', '地名', '固有名詞', '組織名'])
    word2vec_model = Word2VecModel('models/word2vec.gensim.model')
    elastic_model = ElasticModel('http://localhost:9200', 'expb')

    run(host='localhost', port=6300, debug=True, reloader=True)
