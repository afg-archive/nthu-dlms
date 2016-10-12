from urllib.parse import urlparse, parse_qs
import datetime
import lxml.html
import re
import requests


def get_hw_id_from_href(href):
    return parse_qs(urlparse(href).query)['hw'][-1]


deadline_regex = re.compile('(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})')


def parse_deadline(deadline_string):
    match = deadline_regex.match(deadline_string)
    if match is None:
        raise ValueError("Cannot parse deadline {!r}".format(deadline_string))

    return datetime.datetime(*map(int, match.groups()))


noeng_regex = re.compile('[^A-Za-z]+')


def get_zh_course_name(mixed_course_name):
    return noeng_regex.search(mixed_course_name).group()


class Client:
    def __init__(self, username, password):
        self.session = requests.Session()
        self.initialized_at = datetime.datetime.now()

        # login
        self.post('http://lms.nthu.edu.tw/sys/lib/ajax/login_submit.php',
                  {'account': username,
                   'password': password})

    def get(self, url, params):
        return self.response_to_html(self.session.get(url, params=params))

    def post(self, url, data):
        return self.response_to_html(self.session.post(url, data=data))

    @staticmethod
    def response_to_html(response):
        assert response.status_code < 400
        response.encoding = 'utf-8'
        return lxml.html.fromstring(response.text, response.url)

    course_url_prefix = '/course/'

    def iter_courses(self):
        doc = self.get('http://lms.nthu.edu.tw/home.php', {'f': 'allcourse'})
        for a in doc.xpath('//*[@id="right"]/div[2]/div[2]/table/tr/td[2]/a'):
            url = a.attrib['href']
            assert url.startswith(self.course_url_prefix)
            yield a.text, url[len(self.course_url_prefix):]

    def iter_hws_for_course_id(self, course_id):
        doc = self.get('http://lms.nthu.edu.tw/course.php',
                       {'f': 'hwlist',
                        'courseID': course_id})
        for a in doc.xpath(
                '//*[@id="main"]/div[2]/table/tr[position()>1]/td[2]/a[1]'):
            yield (a.text, get_hw_id_from_href(a.attrib['href']))

    def hw_info(self, course_id, hw_id):
        doc = self.get('http://lms.nthu.edu.tw/course.php',
                       {'f': 'hw',
                        'courseID': course_id,
                        'hw': hw_id})
        hand_area_text = doc.xpath('//*[@id="main"]/span/*[last()]/text()[1]')[
            0]
        deadline_text = doc.xpath(
            '//*[@id="main"]//td[text()="期限"]/../td[2]/div/text()[1]')[0]
        deadline = parse_deadline(deadline_text)
        return (hand_area_text, deadline)

    def iter_all_homework(self):
        for course, course_id in self.iter_courses():
            for homework, hw_id in self.iter_hws_for_course_id(course_id):
                hand_area_text, deadline = self.hw_info(course_id, hw_id)
                yield course, homework, deadline, hand_area_text

    def filter_iter_all_homework(self):
        for course, homework, deadline, hat in \
                self.iter_all_homework():
            if hat == '我的作業':
                handed = True
            else:
                handed = False
            if not handed or (deadline > self.initialized_at):
                yield handed, deadline, homework, get_zh_course_name(course)


if __name__ == '__main__':
    import getpass
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--username', help='username for iLMS')
    parser.add_argument('--password', help='password for iLMS')
    args = parser.parse_args()

    if args.username is None:
        username = input('Username: ')
    else:
        username = args.username
    if args.password is None:
        password = getpass.getpass()
    else:
        password = args.password

    hws = sorted(
        Client(username, password).filter_iter_all_homework(),
        key=lambda k: (k[1], k[0])
    )
    for handed, deadline, homework, course in hws:
        print(['未交', '已交'][handed], deadline, homework, course, sep='\t')
