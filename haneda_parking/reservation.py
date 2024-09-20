'''
# 羽田空港駐車場予約プログラム

http://hnd-rsv.aeif.or.jp/airport2/app/toppage
こちらのサイトで駐車場を予約するシステム。P2P3のみ対応

## プログラムを走らせる前の準備

(1) 上記予約サイトで、事前にアカウントを作成
(2) クレジットカードを登録し、また自動車のナンバーを1件だけ登録する（最初のナンバーで予約するように動作する）

## 注意事項
入庫日より1週間以上あることが望ましい。というのは、1週間以下の場合にキャンセル代がかかるため、誤操作などでキャンセル代が発生してしまう。
また、キャンセル代の都合から、ちょうど1週間前にキャンセルが大量に出るためそこが狙いどき

## 必要な情報
- 上記で作ったアカウント（emailアドレスと、ログインパスワード）
- 入庫日と出庫日
- モード（後述）
'''

import argparse
import os
import time
from collections import defaultdict
from datetime import date
from datetime import datetime as dt
from datetime import timedelta
from itertools import takewhile

import selenium
from logzero import logger
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as Ec
from selenium.webdriver.support.ui import Select, WebDriverWait

# now no need to install and specify driver
# https://edaha-room.com/python_selenium_webdriver_error/1954/
# DIRNAME = os.path.dirname(__file__)
# WEBDRIVER = os.path.join(DIRNAME, 'chromedriver-mac-arm64/chromedriver')


class HanedaParkingReserver:
    URL_TOPPAGE = 'http://hnd-rsv.aeif.or.jp/airport2/app/toppage'

    def __init__(self, headless=True, savedir=None):
        chrome_args = {}
        if headless:
            options = Options()
            options.add_argument('--headless')
            chrome_args.update(options=options)
        self.d = selenium.webdriver.Chrome(**chrome_args)
        self.savedir = savedir
        if savedir is not None:
            os.makedirs(savedir, exist_ok=True)
        logger.info(f'{self.URL_TOPPAGE=}')

    def toppage(self, print_debug=False):
        print_debug and logger.debug(f'get {self.URL_TOPPAGE}')
        self.d.get(self.URL_TOPPAGE)
        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.ID, 'cal00')))
        self.save_html('0_toppage_nologin.html')

    def login(self, username, password):
        login_form = self.d.find_element(By.ID, 'command')
        for input in login_form.find_elements(By.TAG_NAME, 'input'):
            name = input.get_attribute('name')
            if name == 'username':
                input.send_keys(username)
            elif name == 'password':
                input.send_keys(password)
        login_btn = login_form.find_element(By.CLASS_NAME, 'btn01')
        login_btn.click()
        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.ID, 'global-nav')))
        logger.info('login')

    def logout(self):
        logout_button = self.d.find_element(By.CLASS_NAME, 'btn01')
        logout_button.click()
        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.CLASS_NAME, 'btn02')))

    def reservation_toppage(self):
        gnav = self.d.find_element(By.ID, 'global-nav')
        for a in gnav.find_elements(By.TAG_NAME, 'a'):
            href = a.get_attribute('href')
            if href.endswith('sentaku'):
                a.click()
                logger.info(f'goto resv page {href}')
                break
        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.ID, 'cal00')))
        time.sleep(0.1)

    def select_date(self, checkin_date, pid=0):
        assert isinstance(checkin_date, date), f'{type(checkin_date)=}'
        checkin_date = checkin_date.strftime('%Y/%m/%d')
        cal_area = self.d.find_element(By.ID, f'cal{pid}0_area')

        cal = cal_area.find_element(By.ID, f'cal{pid}0')
        date_cell_id = f'{pid}-0-{checkin_date}'

        try:
            date_cell = cal.find_element(By.ID, date_cell_id)
        except NoSuchElementException:
            date_cell = None

        if date_cell is None:
            logger.info('next month')
            cal_area.find_element(By.ID, f'cal{pid}0_next').click()
            WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.ID, date_cell_id)))

        date_cell = cal.find_element(By.ID, date_cell_id)
        date_cell_state = date_cell.get_attribute('class')
        if date_cell_state == 'full':
            raise RuntimeError('{date_cell_id}: {date_cell_state}')
        logger.info(f'click {date_cell_id}: {date_cell_state}')
        date_cell.click()
        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.ID, 'nyujohYoteiTime')))

    def select_details(self, checkout_date, checkin_time='12:00', print_debug=False):
        assert isinstance(checkout_date, date), f'{type(checkout_date)=}'

        checkin_input = self.d.find_element(By.ID, 'nyujohYoteiDate')
        checkin_value = checkin_input.get_attribute('value')
        logger.info(f'checkin date = {checkin_value}')

        checkout_selector = Select(self.d.find_element(By.ID, 'nyujohYoteiTime'))
        checkout_selector.select_by_value(checkin_time)
        logger.info(f'checkin time = {checkin_time}')

        checkout_input = self.d.find_element(By.ID, 'shutsujohYoteiDate')
        checkout_input.click()

        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.CLASS_NAME, 'datepicker-days')))
        date_table = self.d.find_element(By.CLASS_NAME, 'datepicker-days')

        current_month = date_table.find_element(By.CLASS_NAME, 'datepicker-switch').text.strip()
        target_month = f'{checkout_date.year}年{checkout_date.month:02}月'
        if current_month != target_month:
            logger.info(f'clicked next ({target_month=} {current_month=})')
            date_table.find_element(By.CLASS_NAME, 'next').click()
            time.sleep(0.1)

        checkout_data_date = str(int(dt(*checkout_date.timetuple()[:3], 9, 0).timestamp()) * 1000)
        logger.warning(f'{checkout_date=}, {checkout_data_date=}')
        for td in date_table.find_elements(By.TAG_NAME, 'td'):
            status = td.get_attribute('class')
            data_date = td.get_attribute('data-date')
            print_debug and logger.warning(f'{status=}, {data_date=}, {td.text=}')
            if status == 'day' and data_date == checkout_data_date:
                td.click()
                break
        else:
            raise RuntimeError()

        car_selector = Select(self.d.find_element(By.ID, 'numberPlateId'))
        logger.info(f'number = {car_selector.options[1].text}')
        car_selector.select_by_index(1)

        next_button = self.d.find_element(By.CLASS_NAME, 'next_button')
        logger.info(f'click {next_button.text}')
        next_button.click()

        try:
            yoyaku_form_error = self.d.find_element(By.CLASS_NAME, 'yoyaku_form_error')
            if yoyaku_form_error:
                error = yoyaku_form_error.find_element(By.TAG_NAME, 'p')
                raise RuntimeError(error.text)
        except NoSuchElementException:
            pass

        WebDriverWait(self.d, 10).until(Ec.visibility_of_element_located((By.ID, 'yoyaku_btn')))

    def confirm(self):
        chkbox_div = self.d.find_element(By.CLASS_NAME, 'chkbox')
        chkbox_label = chkbox_div.find_element(By.TAG_NAME, 'label')
        logger.info(chkbox_label.text)
        chkbox_label.click()

        WebDriverWait(self.d, 10).until(Ec.element_to_be_clickable((By.ID, 'yoyaku_btn')))
        button = self.d.find_element(By.ID, 'yoyaku_btn')
        button.click()
        time.sleep(3)

    def save_html(self, path):
        if self.savedir is None:
            return
        path = os.path.join(self.savedir, path)
        with open(path, 'w') as fout:
            print(self.d.page_source, file=fout)
        logger.debug(f'saved to {path}')

    def get_calenders(self, print_debug=False):
        self.toppage(print_debug)

        out = defaultdict(dict)
        for pid in (0, 1, 0, 1):

            cal = self.d.find_element(By.ID, f'cal{pid}0')
            for td in cal.find_elements(By.TAG_NAME, 'td'):
                cell_id = td.get_attribute('id')
                date = cell_id.split('-')[-1]
                status = td.get_attribute('class')
                print_debug and logger.debug(f'{cell_id} status = {status}')
                if status and status != 'full':
                    out[pid][date] = status

            prev_style = self.d.find_element(By.ID, f'cal{pid}0_prev').get_attribute('style')
            if 'none' in prev_style:
                self.d.find_element(By.ID, f'cal{pid}0_next').click()
                time.sleep(0.1)

        return dict(out)

    def make_reservation(self, user, password, pid, checkin_date, checkout_date, test_only=False):
        self.toppage()
        self.save_html('1_toppage.html')

        self.login(user, password)
        self.save_html('2_loginpage.html')

        self.reservation_toppage()
        self.save_html('3_resvtop.html')

        self.select_date(checkin_date, pid)
        self.save_html('4_resvpage.html')

        self.select_details(checkout_date)
        self.save_html('5_confirmpage.html')

        if not test_only:
            self.confirm()
            self.save_html('6_done.html')
        self.logout()


PARKING_NAMES = ('P2', 'P3')


def reservation_main(user, password, checkin_date, days, min_days=None,
                     parking=None, test_only=False, headless=False, print_debug=False, debug=False):
    '''
    【注意点】
    - 予約時間は「正午」に設定されているので、のちに変更する必要がある。
      予約時間を2時間遅れるとキャンセルされるので注意。一方で早まる分にはいくらでも良い。
    - 連続して取れるようにしたいが、現状、予約を取ったらexit()するようにしている。
    '''

    logger.info('reservation_main(' + ', '.join(f'{k}={v}' for k, v in locals().items()) + ')')

    parkings = (0, 1) if parking is None else (PARKING_NAMES.index(parking),)
    target_dates = {p: [(checkin_date + timedelta(days=d)).strftime('%Y/%m/%d') for d in range(days)] for p in parkings}

    logger.info('target:')
    for i, d in target_dates.items():
        logger.info(f'  {PARKING_NAMES[i]}: {d}')

    if test_only:
        logger.info('TEST ONLY / NO CONFIRM RESERVATION')

    r = HanedaParkingReserver(headless=headless)
    prev = {}
    while True:
        try:
            cals = r.get_calenders(print_debug)
            for pid, cal_table in cals.items():
                if pid not in target_dates:
                    continue

                if print_debug or prev.get(pid) != cal_table:
                    logger.info(f'------ {PARKING_NAMES[pid]}')
                    logger.info(f' target: {target_dates[pid]} days from {checkin_date}')
                    logger.info(f' availability: {cal_table}')
                    prev[pid] = cal_table

                if target_dates[pid][0] not in cal_table:
                    continue

                logger.info(f'{target_dates=}')

                available_dates = list(takewhile(lambda x: x in cal_table, target_dates[pid]))
                if len(available_dates) < (min_days or days):
                    logger.warning(f'{len(available_dates)=} < {min_days=}')
                    continue

                logger.info(f'=================== making revervation on {available_dates} at {PARKING_NAMES[pid]}')
                checkin_date = dt.strptime(available_dates[0], '%Y/%m/%d')
                checkout_date = dt.strptime(available_dates[-1], '%Y/%m/%d')
                r.make_reservation(user, password, pid, checkin_date, checkout_date, test_only=test_only)
                logger.info(f'successfully booked {available_dates} on cal:{pid} (test_only={test_only})')

                # update target date
                remaining_dates = [d for d in target_dates[pid] if d not in available_dates]

                if not remaining_dates:
                    logger.debug('booked all days. done.')
                    return

                logger.info(f'update target {remaining_dates}')
                target_dates = {pid: remaining_dates}

        except Exception as e:
            if debug:
                raise
            logger.exception(e)

        time.sleep(1)

    exit()


def parse_date(s):
    return dt.strptime(s, '%Y/%m/%d').date()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', required=True)
    parser.add_argument('-p', '--password', required=True)
    parser.add_argument('checkin_date', type=parse_date, help='format YYYY/mm/dd')
    parser.add_argument('-d', '--days', type=int, required=True, help='including check-in day')
    parser.add_argument('-m', '--min-days', type=int, default=None, help='minimum days to book')
    parser.add_argument('-P', '--parking', choices=PARKING_NAMES, help='default both')

    parser.add_argument('--test', dest='test_only', action='store_true', help='skip ')
    parser.add_argument('--head', dest='headless', action='store_false')
    parser.add_argument('-v', '--verbose', action='count')
    parser.add_argument('--debug', action='store_true', help='raise error')

    args = parser.parse_args()
    assert args.min_days is None or args.days >= args.min_days

    # warn cancelation policy
    days_left = args.checkin_date - dt.today().date()
    if days_left.days < 8:
        logger.error(f'WARNING: only {days_left} days left')

    reservation_main(args.user, args.password, args.checkin_date, args.days, args.min_days,
                     parking=args.parking, test_only=args.test_only, headless=args.headless,
                     print_debug=args.verbose, debug=args.debug)


if __name__ == '__main__':
    main()
