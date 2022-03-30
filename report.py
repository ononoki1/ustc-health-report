import argparse
import datetime
import io
import json
import re

import PIL
import pytesseract
import pytz
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
        login_success = False
        session = self.login()
        cookies = session.cookies
        get_form = session.get("https://weixine.ustc.edu.cn/2020")
        if get_form.url != "https://weixine.ustc.edu.cn/2020/home":
            print("Login failed.")
        else:
            print("Login succeeded.")
            login_success = True
        if not login_success:
            return False
        print('Start daily report.')
        data = get_form.text
        data = data.encode('ascii', 'ignore').decode('utf-8', 'ignore')
        soup = BeautifulSoup(data, 'html.parser')
        token = soup.find("input", {"name": "_token"})['value']
        with open(self.data_path, "r+") as f:
            data = f.read()
            data = json.loads(data)
            data["jinji_lxr"] = self.emer_person
            data["jinji_guanxi"] = self.relation
            data["jiji_mobile"] = self.emer_phone
            data["dorm_building"] = self.dorm
            data["dorm"] = self.dorm_room
            data["_token"] = token
        headers = {'authority': 'weixine.ustc.edu.cn', 'origin': 'https://weixine.ustc.edu.cn',
                   'upgrade-insecure-requests': '1', 'content-type': 'application/x-www-form-urlencoded',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.100 Safari/537.36',
                   'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                   'referer': 'https://weixine.ustc.edu.cn/2020/home', 'accept-language': 'zh-CN,zh;q=0.9',
                   'Connection': 'close',
                   'cookie': "PHPSESSID=" + cookies.get("PHPSESSID") + ";XSRF-TOKEN=" + cookies.get(
                       "XSRF-TOKEN") + ";laravel_session=" + cookies.get("laravel_session"), }
        url = "https://weixine.ustc.edu.cn/2020/daliy_report"
        session.post(url, data=data, headers=headers)
        data = session.get("https://weixine.ustc.edu.cn/2020").text
        soup = BeautifulSoup(data, 'html.parser')
        pattern = re.compile("202[0-9]-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
        token = soup.find("span", {"style": "position: relative; top: 5px; color: #666;"})
        flag = False
        if pattern.search(token.text) is not None:
            date = pattern.search(token.text).group()
            date = date + " +0800"
            report_time = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S %z")
            time_now = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
            delta = time_now - report_time
            delta_negative = report_time - time_now
            if delta.seconds < 120 or delta_negative.seconds < 120:
                flag = True
        if not flag:
            print("Daily report failed.")
        else:
            print("Daily report succeeded.")
        ret = session.get("https://weixine.ustc.edu.cn/2020/apply/daliy/i")
        if ret.status_code == 200:
            print("Start cross-campus report.")
            data = ret.text
            data = data.encode('ascii', 'ignore').decode('utf-8', 'ignore')
            soup = BeautifulSoup(data, 'html.parser')
            token2 = soup.find("input", {"name": "_token"})['value']
            start_date = soup.find("input", {"id": "start_date"})['value']
            end_date = soup.find("input", {"id": "end_date"})['value']
            report_url = "https://weixine.ustc.edu.cn/2020/apply/daliy/post"
            report_data = {'_token': token2, 'start_date': start_date, 'end_date': end_date,
                           "return_college[]": {"东校区", "西校区", "南校区", "北校区", "中校区"}, "t": 3}
            ret = session.post(url=report_url, data=report_data)
            if ret.status_code == 200:
                print('Cross-campus report succeeded.')
            else:
                flag = False
                print('Cross-campus report failed.')
        return flag

    def login(self):
        retries = Retry(total=3, backoff_factor=0.5,
                        status_forcelist=[500, 502, 503, 504])
        s = requests.Session()
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.headers[
            "User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36 Edg/92.0.902.67 "
        url = "https://passport.ustc.edu.cn/login?service=http%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin"
        r = s.get(
            url, params={"service": "https://weixine.ustc.edu.cn/2020/caslogin"})
        x = re.search(r"""<input.*?name="CAS_LT".*?>""", r.text).group(0)
        cas_lt = re.search(r'value="(LT-\w*)"', x).group(1)
        cas_captcha_url = "https://passport.ustc.edu.cn/validatecode.jsp?type=login"
        r = s.get(cas_captcha_url)
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
        data = {'model': 'uplogin.jsp', 'service': 'https://weixine.ustc.edu.cn/2020/caslogin',
                'username': self.student_id, 'password': str(self.password), 'warn': '', 'showCode': '1', 'button': '',
                'CAS_LT': cas_lt, 'LT': lt_code}
        s.post(url, data=data)
        return s


if __name__ == "__main__":
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
