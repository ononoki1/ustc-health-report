import argparse
import datetime
import io
import json
import re

import PIL
import pytesseract
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Report(object):
    def __init__(self, student_id, password, data_path, emer_person, relation, emer_phone, dorm, dorm_room, xc, ak, force):
        self.student_id = student_id
        self.password = password
        self.data_path = data_path
        self.emer_person = emer_person
        self.relation = relation
        self.emer_phone = emer_phone
        self.dorm = dorm
        self.dorm_room = dorm_room
        self.pic = [xc, ak]
        self.force = force
        self.session = None
        self.token = None

    def login(self):
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.headers['user-agent'] = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'
        url = 'https://passport.ustc.edu.cn/login?service=http%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin'
        r = self.session.get(url, params={'service': 'https://weixine.ustc.edu.cn/2020/caslogin'})
        x = re.search(r'<input.*?name="CAS_LT".*?>', r.text).group(0)
        cas_lt = re.search(r'value="(LT-\w*)"', x).group(1)
        r = self.session.get('https://passport.ustc.edu.cn/validatecode.jsp?type=login')
        img = PIL.Image.open(io.BytesIO(r.content))
        pix = img.load()
        for i in range(img.size[0]):
            for j in range(img.size[1]):
                r, g, _ = pix[i, j]
                if g >= 40 and r < 80:
                    pix[i, j] = (0, 0, 0)
                else:
                    pix[i, j] = (255, 255, 255)
        lt_code = pytesseract.image_to_string(img).strip()
        data = {'CAS_LT': cas_lt, 'LT': lt_code, 'button': '', 'model': 'uplogin.jsp', 'password': self.password,
                'service': 'https://weixine.ustc.edu.cn/2020/caslogin', 'showCode': '1', 'username': self.student_id,
                'warn': ''}
        self.session.post(url, data=data)
        if self.session.get('https://weixine.ustc.edu.cn/2020').url == 'https://weixine.ustc.edu.cn/2020/home':
            print('Login succeeded.')
            return True
        else:
            print('Login failed.')
        return False

    def daily(self):
        cookies = self.session.cookies
        get_form = self.session.get('https://weixine.ustc.edu.cn/2020')
        self.token = BeautifulSoup(get_form.text, 'html.parser').find('input', {'name': '_token'})['value']
        with open(self.data_path, 'r+') as f:
            data = json.loads(f.read())
            data['_token'] = self.token
            data['jinji_lxr'] = self.emer_person
            data['jinji_guanxi'] = self.relation
            data['jiji_mobile'] = self.emer_phone
            data['dorm_building'] = self.dorm
            data['dorm'] = self.dorm_room
        header = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                  'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                  'authority': 'weixine.ustc.edu.cn', 'origin': 'https://weixine.ustc.edu.cn', 'connection': 'close',
                  'content-type': 'application/x-www-form-urlencoded',
                  'cookie': 'PHPSESSID=' + cookies.get('PHPSESSID') + ';XSRF-TOKEN=' + cookies.get(
                      'XSRF-TOKEN') + ';laravel_session=' + cookies.get('laravel_session'),
                  'referer': 'https://weixine.ustc.edu.cn/2020/home', 'upgrade-insecure-requests': '1',
                  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'}
        url = 'https://weixine.ustc.edu.cn/2020/daliy_report'
        self.session.post(url, data=data, headers=header)
        if self.session.get('https://weixine.ustc.edu.cn/2020/home').text.find('text-success') != -1:
            print('Daily report succeeded.')
            return True
        else:
            print('Daily report failed.')
        return False

    def upload(self):
        already_upload = False
        if self.session.get(
                'https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=3').url == 'https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=3':
            print('Health information already uploaded.')
            already_upload = True
            if self.force != 'force':
                return True
        r = self.session.get('https://weixine.ustc.edu.cn/2020/upload/xcm')
        if r.text.find('关闭相关功能') != -1:
            print('Health information upload is unavailable.')
            return already_upload
        else:
            for index, name in ((1, 'xc'), (2, 'ak')):
                ret = self.session.get(self.pic[index - 1])
                blob = ret.content
                url = 'https://weixine.ustc.edu.cn/2020img/api/upload_for_student'
                search_payload = r'''formData:{
                    _token:  '(\w{40})',
                    'gid': '(\d{10})',
                    'sign': '(\S{36})',
                    't' : 1
                }'''
                gid = re.search(search_payload, r.text).group(1);
                sign = re.search(search_payload, r.text).group(2);
                payload = {'_token': self.token, 'gid': gid, 'id': f'WU_FILE_{index}',
                           'lastModifiedDate': datetime.datetime.now().strftime(
                               '%a %b %d %Y %H:%M:%S GMT+0800 (China Standard Time)'),
                           'name': f'{name}.png', 'sign': sign, 'size': f'{len(blob)}', 't': index, 'type': 'image/png'}
                headers_upload = self.session.headers
                headers_upload['user-agent'] = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'
                self.session.post(url, data=payload, files={'file': (payload['name'], blob)}, headers=headers_upload)
        if self.session.get(
                'https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=3').url == 'https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=3':
            print('Health information upload succeeded.')
            return True
        else:
            print('Health information upload failed.')
        return False

    def cross(self):
        soup = BeautifulSoup(self.session.get('https://weixine.ustc.edu.cn/2020/apply/daliy/i').text, 'html.parser')
        start_date = soup.find('input', {'id': 'start_date'})['value']
        end_date = soup.find('input', {'id': 'end_date'})['value']
        report_url = 'https://weixine.ustc.edu.cn/2020/apply/daliy/ipost'
        report_data = {'_token': self.token, 'end_date': end_date, 'reason': '取快递',
                       'return_college[]': {'东校区', '西校区', '南校区', '北校区', '中校区'}, 'start_date': start_date, 't': 3}
        if self.session.post(url=report_url, data=report_data, allow_redirects=False).status_code == 302:
            print('Cross-campus report succeeded.')
            return True
        else:
            print('Cross-campus report failed.')
        return False

    def report(self):
        if self.login() and self.daily() and self.upload() and self.cross():
            return True
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('student_id')
    parser.add_argument('password')
    parser.add_argument('data_path')
    parser.add_argument('emer_person')
    parser.add_argument('relation')
    parser.add_argument('emer_phone')
    parser.add_argument('dorm')
    parser.add_argument('dorm_room')
    parser.add_argument('xc')
    parser.add_argument('ak')
    parser.add_argument('force')
    args = parser.parse_args()
    if not Report(student_id=args.student_id, password=args.password, data_path=args.data_path,
                  emer_person=args.emer_person, relation=args.relation, emer_phone=args.emer_phone, dorm=args.dorm,
                  dorm_room=args.dorm_room, xc=args.xc, ak=args.ak, force=args.force).report():
        exit(1)
