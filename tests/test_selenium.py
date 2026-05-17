import re
import threading
import time
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server
from app import create_app, db, fake
from app.models import Role, User, Post


class SeleniumTestCase(unittest.TestCase):
    client = None
    server = None
    base_url = None
    
    @classmethod
    def setUpClass(cls):
        # start Chrome
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')  # 以无头模式启动Chrome,即启动浏览器却不弹出窗口
        options.add_argument('--window-size=1280,800')
        try:
            cls.client = webdriver.Chrome(options=options)
        except Exception as e:
            cls.client = None
            print(f'Chrome WebDriver unavailable: {e}')

        # skip these tests if the browser could not be started
        if cls.client:
            # create the application
            cls.app = create_app('testing')
            cls.app_context = cls.app.app_context()
            cls.app_context.push()

            # suppress logging to keep unittest output clean
            import logging
            logger = logging.getLogger('werkzeug')  # Flask 开发服务器底层用的是 Werkzeug,设置为Error后,Info,Warning信息不输出
            logger.setLevel("ERROR")

            # create the database and populate with some fake data
            db.create_all()
            Role.insert_roles()
            fake.users(10)
            fake.posts(10)

            # add an administrator user
            admin_role = Role.query.filter_by(name='Administrator').first()
            admin = User(email='john@example.com',
                         username='john', password='cat',
                         role=admin_role, confirmed=True)
            db.session.add(admin)
            db.session.commit()

            # start the Flask server in a thread
            cls.server = make_server('127.0.0.1', 0, cls.app)
            cls.base_url = 'http://127.0.0.1:%s' % cls.server.server_port
            cls.server_thread = threading.Thread(target=cls.server.serve_forever)
            cls.server_thread.daemon = True
            cls.server_thread.start()

            # give the server a second to ensure it is up
            time.sleep(1) 

    @classmethod
    def tearDownClass(cls):
        if cls.client:
            # stop the flask server and the browser
            cls.client.quit()
            cls.server.shutdown()
            cls.server_thread.join()

            # destroy database
            db.drop_all()
            db.session.remove()

            # remove application context
            cls.app_context.pop()

    def setUp(self):
        if not self.client:
            self.skipTest('Web browser not available')

    def tearDown(self):
        pass
    
    def test_admin_home_page(self):
        # navigate to home page
        self.client.get(self.base_url + '/')
        self.assertTrue(re.search(r'Hello,\s+Stranger!',
                                  self.client.page_source))

        # navigate to login page
        self.client.find_element(
            By.CSS_SELECTOR, 'a[href$="/auth/login"]').click()
        self.assertIn('<h1>Login</h1>', self.client.page_source)

        # login
        self.client.find_element(By.NAME, 'email').\
            send_keys('john@example.com')
        self.client.find_element(By.NAME, 'password').send_keys('cat')
        self.client.find_element(By.NAME, 'submit').click()
        WebDriverWait(self.client, 10).until(
            EC.text_to_be_present_in_element((By.TAG_NAME, 'h1'), 'Hello, john!')
        )
        self.assertTrue(re.search(r'Hello,\s+john!', self.client.page_source))

        # navigate to the user's profile page
        self.client.find_element(
            By.CSS_SELECTOR, 'a[href$="/user/john"]').click()
        self.assertIn('<h1>john</h1>', self.client.page_source)
