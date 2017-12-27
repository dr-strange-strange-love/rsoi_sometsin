
from requests.exceptions import ReadTimeout
from queue import Queue
import json
import requests

from aggregation_service import application


reset_billing_total_q = Queue()
statistics_q_async = Queue()
statistics_q_sync = Queue()


def reset_billing_total_queue():
    while True:
        url = reset_billing_total_q.get(block = True, timeout = None)
        print(url)
        try:
            r = requests.patch(url, json = json.dumps({'total': 0}), timeout = 1)
        except ReadTimeout as err:
            reset_billing_total_q.put(url)

# url, method, payload, headers, job, user, time, count, hash, status
def statistics_queue_async():
    count_max = 5

    while True:
        queueload = statistics_q_async.get(block = True, timeout = None)
        if not queueload.get('count', None):
            queueload['count'] = 0
        print(queueload)

        if queueload['count'] >= count_max:
            queueload['status'] = 'timedout'
            requests.patch('http://127.0.0.1:8005/report', json = json.dumps(queueload), timeout = 2)
        else:
            try:
                if queueload['method'] == 'POST':
                    r = requests.post(queueload['url'], json = json.dumps(queueload['payload']), headers = queueload['headers'], timeout = 5)
                elif queueload['method'] == 'PATCH':
                    r = requests.patch(queueload['url'], json = json.dumps(queueload['payload']), headers = queueload['headers'], timeout = 5)
                else: # DELETE
                    r = requests.delete(queueload['url'], headers = queueload['headers'], timeout = 5)
                queueload['msg_json'] = r.json()

                if r.status_code in [400, 401, 403, 404, 500, 503]:
                    queueload['status'] = 'failure'
                    queueload['status_code'] = r.status_code
                    requests.patch('http://127.0.0.1:8005/report', json = json.dumps(queueload), timeout = 2)
                else:
                    queueload['status'] = 'success'
                    requests.patch('http://127.0.0.1:8005/report', json = json.dumps(queueload), timeout = 2)
            except ReadTimeout as err:
                queueload['count'] = queueload['count'] + 1
                statistics_q_async.put(queueload)

# job, status, user, time, count, hash
def statistics_queue_sync():
    count_max = 10

    while True:
        queueload = statistics_q_sync.get(block = True, timeout = None)
        if not queueload.get('count', None):
            queueload['count'] = 0
        print(queueload)

        if queueload['count'] >= count_max:
            application.logger.warning('Cant deliver syncronous statistics queuload: {}'.format(queueload))
        else:
            try:
                requests.patch('http://127.0.0.1:8005/report', json = json.dumps(queueload), timeout = 2)
            except ReadTimeout as err:
                queueload['count'] = queueload['count'] + 1
                statistics_q_sync.put(queueload)
