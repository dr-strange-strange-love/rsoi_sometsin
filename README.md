1. Clone repo to /srv/www:
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

6. Prepare configs:
```
$ cp rsoi_nginx.conf /etc/nginx/conf.d
$ cp ./aggregation_service/aggregation.service /etc/systemd/system
$ cp ./goods_service/goods.service /etc/systemd/system
$ cp ./orders_service/orders.service /etc/systemd/system
$ cp ./billing_service/billing.service /etc/systemd/system
```

7. Launch services:
```
$ systemctl start/stop/restart/enable aggregation
$ systemctl start/stop/restart/enable goods
$ systemctl start/stop/restart/enable orders
$ systemctl start/stop/restart/enable billing
$ systemctl start/stop/restart/enable nginx
```

8. Check logs:
```
$ journalctl --unit aggregation/goods/orders/billing
$ nano /var/log/nginx/error.log
```