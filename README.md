1. Clone repo:
```
$ git clone https://github.com/dr-strange-strange-love/rsoi_sometsin.git rsoi_services
```

2. Get ready:
```
$ cd rsoi_services
```

3. Install python 3.6 (anaconda would do) and create virtualenv, e.g.:
```
$ conda create -n rsoi_env_36 python=3.6
```

4. Install dependencies (pip):
```
certifi==2017.11.5
chardet==3.0.4
click==6.7
coverage==4.4.2
Flask==0.12.2
Flask-Login==0.4.0
gunicorn==19.7.1
idna==2.6
itsdangerous==0.24
Jinja2==2.9.6
MarkupSafe==1.0
requests==2.18.4
tinydb==3.6.0
urllib3==1.22
Werkzeug==0.12.2
```

4. Run services:
```
$ cd aggregation_service && gunicorn -b 127.0.0.1:8000 wsgi:application&
$ cd goods_service && gunicorn -b 127.0.0.1:8001 wsgi:application&
$ cd orders_service && gunicorn -b 127.0.0.1:8002 wsgi:application&
$ cd billing_service && gunicorn -b 127.0.0.1:8003 wsgi:application&
```

5. Test services:
```
$ coverage run -m goods_service.goods_test
$ coverage run -m orders_service.orders_test
$ coverage run -m billing_service.billing_test
$ coverage report -m
```
