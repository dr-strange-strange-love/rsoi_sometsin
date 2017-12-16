
from tinydb import TinyDB, Query

try:
    statistics_db = TinyDB('/Users/amadeus/Documents/rsoi_services/warehouse/statistics_db.json')
except:
    statistics_db = TinyDB('/srv/www/rsoi_services/warehouse/statistics_db.json')
Stats = Query()


def push_event(job, status, user, time, msg_json=None, status_code=None, url=None, payload=None):
    statistics_db.insert({
        'job': job,
        'status': status,
        'user': user,
        'time': time,
        'msg_json': msg_json,
        'status_code': status_code,
        'url': url,
        'payload': payload
    })

def get_user_login_data():
    return statistics_db.search(Stats.job == 'user login')

def get_user_bill_update_data():
    return statistics_db.search(Stats.job == 'bill update')

def get_ops_status():
    jobs = statistics_db.all()
    ops = dict()

    for job in jobs:
        if not ops.get(job['job'], None):
            ops[job['job']] = {'success': 0, 'failure': 0, 'timedout': 0, 'total': 0}
        if job['status'] == 'success':
            ops[job['job']]['success'] = ops[job['job']]['success'] + 1
            ops[job['job']]['total'] = ops[job['job']]['total'] + 1
        elif job['status'] == 'failure':
            ops[job['job']]['failure'] = ops[job['job']]['failure'] + 1
            ops[job['job']]['total'] = ops[job['job']]['total'] + 1
        else: # timedout
            ops[job['job']]['timedout'] = ops[job['job']]['timedout'] + 1
            ops[job['job']]['total'] = ops[job['job']]['total'] + 1

    return ops
