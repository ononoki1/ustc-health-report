import argparse
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
    def __init__(self, student_id, password, data_path, emer_person, relation, emer_phone, dorm, dorm_room):
        self.student_id = student_id
        self.password = password
        self.data_path = data_path
        self.emer_person = emer_person
        self.relation = relation
        self.emer_phone = emer_phone
        self.dorm = dorm
        self.dorm_room = dorm_room

    def report(self):
        session = self.login()
        cookies = session.cookies
        get_form = session.get('https://weixine.ustc.edu.cn/2020')
        if get_form.url == 'https://weixine.ustc.edu.cn/2020/home':
            print('Login succeeded.')
        else:
            print('Login failed.')
            return False
        print('Start daily report.')
        token = BeautifulSoup(get_form.text, 'html.parser').find('input', {'name': '_token'})['value']
        with open(self.data_path, 'r+') as f:
            data = json.loads(f.read())
            data['_token'] = token
            data['dorm'] = self.dorm_room
            data['dorm_building'] = self.dorm
            data['jinji_guanxi'] = self.relation
            data['jinji_lxr'] = self.emer_person
            data['jiji_mobile'] = self.emer_phone
        header = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                  'accept-language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                  'authority': 'weixine.ustc.edu.cn', 'origin': 'https://weixine.ustc.edu.cn',
                  'connection': 'close', 'content-type': 'application/x-www-form-urlencoded',
                  'cookie': 'PHPSESSID=' + cookies.get('PHPSESSID') + ';XSRF-TOKEN=' + cookies.get(
                      'XSRF-TOKEN') + ';laravel_session=' + cookies.get('laravel_session'),
                  'referer': 'https://weixine.ustc.edu.cn/2020/home', 'upgrade-insecure-requests': '1',
                  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'}
        url = 'https://weixine.ustc.edu.cn/2020/daliy_report'
        session.post(url, data=data, headers=header)
        if session.get('https://weixine.ustc.edu.cn/2020/home').text.find('text-success') != -1:
            print('Daily report succeeded.')
        else:
            print('Daily report failed.')
            return False
        print('Start cross-campus report.')
        if (session.get(
                'https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=3').url == 'https://weixine.ustc.edu.cn/2020/upload/xcm'):
            print('Upload health information manually to make cross-campus report.')
            return False
        soup = BeautifulSoup(session.get('https://weixine.ustc.edu.cn/2020/apply/daliy/i').text, 'html.parser')
        token = soup.find('input', {'name': '_token'})['value']
        start_date = soup.find('input', {'id': 'start_date'})['value']
        end_date = soup.find('input', {'id': 'end_date'})['value']
        report_url = 'https://weixine.ustc.edu.cn/2020/apply/daliy/post'
        report_data = {'_token': token, 'end_date': end_date, 'reason': '取快递',
                       'return_college[]': {'东校区', '西校区', '南校区', '北校区', '中校区'}, 'start_date': start_date, 't': 3}
        ret = session.post(url=report_url, data=report_data)
        if ret.status_code == 200:
            print('Cross-campus report succeeded.')
        else:
            print('Cross-campus report failed.')
            return False
        return True

    def login(self):
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        s = requests.Session()
        s.mount('https://', HTTPAdapter(max_retries=retries))
        s.headers['user-agent'] = 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'
        url = 'https://passport.ustc.edu.cn/login?service=http%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin'
        r = s.get(url, params={'service': 'https://weixine.ustc.edu.cn/2020/caslogin'})
        x = re.search(r'<input.*?name="CAS_LT".*?>', r.text).group(0)
        cas_lt = re.search(r'value="(LT-\w*)"', x).group(1)
        r = s.get('https://passport.ustc.edu.cn/validatecode.jsp?type=login')
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
        data = {'CAS_LT': cas_lt, 'LT': lt_code, 'button': '', 'model': 'uplogin.jsp', 'password': str(self.password),
                'service': 'https://weixine.ustc.edu.cn/2020/caslogin', 'showCode': '1', 'username': self.student_id,
                'warn': ''}
        s.post(url, data=data)
        return s


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data_path', type=str)
    parser.add_argument('stuid', type=str)
    parser.add_argument('password', type=str)
    parser.add_argument('emer_person', type=str)
    parser.add_argument('relation', type=str)
    parser.add_argument('emer_phone', type=str)
    parser.add_argument('dorm', type=str)
    parser.add_argument('dorm_room', type=str)
    args = parser.parse_args()
    if not Report(student_id=args.stuid, password=args.password, data_path=args.data_path, emer_person=args.emer_person,
                  relation=args.relation, emer_phone=args.emer_phone, dorm=args.dorm,
                  dorm_room=args.dorm_room).report():
        exit(1)
