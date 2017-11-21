
from requests.exceptions import ReadTimeout
from queue import Queue
import json
import requests

reset_billing_total_q = Queue()


def reset_billing_total_queue():
    while True:
        url = reset_billing_total_q.get(block = True, timeout = None)
        print(url)
        try:
            r = requests.patch(url, json = json.dumps({'total': 0}), timeout = 1)
        except ReadTimeout as err:
            reset_billing_total_q.put(url)
