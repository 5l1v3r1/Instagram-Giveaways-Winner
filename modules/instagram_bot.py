from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import WebDriverException
from typing import List, Iterator, Callable
from itertools import chain
from time import perf_counter, sleep
import re
import sys
import os
from pathlib import Path
import json

class Comments:
    
    def __init__(self, iter_connections:Iterator[str], parts_expr:List[str]):
        self.iter_connections = iter_connections
        self.parts_expr = parts_expr

    def generate(self) -> Iterator[str]:

        last_part = self.parts_expr[-1]

        while True:

            if len(self.parts_expr) == 1:
                yield last_part

            else:
            
                try:
                
                    users = next(self.iter_connections)
                except StopIteration:
                    return

                comment = ''.join(chain.from_iterable(zip(self.parts_expr, users)))

                yield (comment + last_part).replace(r'\@', '@')


class Bot:

    __version__ = '1.2.3'

    
    def __init__(self, window:bool=True, timeout:int=30, binary_location:str=None, default_lang:bool=False):
        
        if sys.platform == 'linux' or sys.platform == 'linux2':
            driver_file_name = 'chrome_linux'
        elif sys.platform == 'win32':
            driver_file_name = 'chrome_windows.exe'
        elif sys.platform == 'darwin':
            driver_file_name = 'chrome_mac'
            
        driver_path = os.path.join(os.getcwd() , f'drivers{os.path.sep}{driver_file_name}')
        
        os.chmod(driver_path , 0o755) 

        options = webdriver.ChromeOptions()

        if not default_lang:
            options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'})

        options.headless = not window ;

        if binary_location:
            options.binary_location = binary_location

        
        self.driver = webdriver.Chrome(executable_path=driver_path, options=options)


        self.url_base = 'https://www.instagram.com/'
        self.url_login = self.url_base + 'accounts/login'
        self.timeout = timeout

    def log_in(self, username:str, password:str):

        COOKIE_NAME = 'sessionid'
        
        self.driver.get(self.url_login)

        try:

            with open(f'cookies/{username}.json', 'r') as file:
                cookie = json.load(file)

        except FileNotFoundError:
            pass
        
        else:
            self.driver.add_cookie(cookie)

            # I find out that chrome sends a warning message after loading a cookie
            WebDriverWait(self.driver, self.timeout).until(
                lambda x: self.driver.get_log('browser'))
            
            self.driver.refresh()


        # Waits for information about logged status
        WebDriverWait(self.driver, self.timeout).until(
            lambda x: x.find_elements_by_css_selector('form input'))


        if 'not-logged-in' in self.driver.find_element_by_tag_name('html').get_attribute('class'):

            # Waits for form
            WebDriverWait(self.driver, self.timeout).until(
                lambda x: x.find_elements_by_css_selector('form input'))
            
            username_input, password_input, *_ = self.driver.find_elements_by_css_selector('form input')

            username_input.send_keys(username)
            password_input.send_keys(password + Keys.ENTER)

            WebDriverWait(self.driver, self.timeout).until(
                lambda x: 'js logged-in' in x.find_element_by_tag_name('html').get_attribute('class'))
            
            cookie = self.driver.get_cookie(COOKIE_NAME)

            Path('cookies/').mkdir(exist_ok=True)

            with open(f'cookies/{username}.json', 'w') as file:
                json.dump(cookie, file)


    def new_tab(self, url:str='https://www.google.com'):
        
        self.driver.execute_script(f'window.open(\'{url}\');')
        self.driver.switch_to.window(self.driver.window_handles[-1])
        

    def close_tab(self):
        
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[-1]) # could write 'main' but later on could be modified
        
    
    def get_user_connections(self, username:str, limit:int=None, followers=True) -> List[str]:

        '''

        Connections means followers or followings depending on the chosen data

        Args:
            - username : target's username
            - limit : limit number of connections to save
            - followers: if True returns a list of user's followers, if False returns of user's followings

        Returns:
            - list of usernames
        '''
        
        if limit == 0:
            return []

        path = 'records//' + ('followers' if followers else 'followings')

        if limit:

            try:
                
                with open(f'{path}//{username}_{limit}.json', 'r') as file:
                    return json.load(file)
                
            except FileNotFoundError:
                pass
        
        self.new_tab(self.url_base + username)

        WebDriverWait(self.driver, self.timeout).until(
            lambda x: x.find_element_by_css_selector('header h1'))
        
        if followers:
            connections_link = self.driver.find_element_by_css_selector('ul li a span')
            connections_limit = int(connections_link.get_attribute('title').replace(',', '').replace('.', '').replace(' ', ''))
        else:
            connections_link = self.driver.find_element_by_css_selector('ul li:nth-child(3) a span')

            try:
                connections_limit = int(connections_link.text.replace(',', ''))
                
            except ValueError:
                exit('''
                        You must choose a UserTarget which following < 10,000 users
                        This happens because instagram doesn't provide by source the whole number,
                        and it would be a pain to translate every possible letter
                    ''')

        limit = min(connections_limit, limit) if limit else connections_limit

        if limit == connections_limit:
            try:
                
                with open(f'{path}//{username}_{limit}.json', 'r') as file:
                    self.close_tab()
                    return json.load(file)
                
            except FileNotFoundError:
                pass
                
        connections_link.click()

        WebDriverWait(self.driver, self.timeout).until(
            lambda x: x.find_element_by_css_selector('div[role=dialog] ul'))
        
        connections_list = self.driver.find_element_by_css_selector('div[role=dialog] ul')
        connections_count = len(connections_list.find_elements_by_css_selector('li'))
        
        last_count = connections_count

        timestamp = perf_counter()

        try:
            if limit != connections_limit:
                raise FileNotFoundError # Already searched and not found

            file = open(f'{path}//{username}_{limit}.json', 'r')
        
        except FileNotFoundError:

            self.driver.execute_script('''
                elem = document.querySelector('div[role=dialog] > div > div:nth-of-type(2)');
            ''')
            
            while connections_count < limit and perf_counter() - timestamp < self.timeout:

                self.driver.execute_script('''
                    elem.scrollTo(0,elem.scrollHeight);
                ''')

                if last_count != connections_count:
                    timestamp = perf_counter()
                
                last_count = connections_count

                connections_count = len(connections_list.find_elements_by_tag_name('li'))

            connections = []
        
            for connection_obj in connections_list.find_elements_by_tag_name('li'):
                connection = connection_obj.find_element_by_tag_name('a')

                connection_name = connection.text

                if not connection_name:
                    connection_name = connection.get_attribute('href').split('/')[-2]

                connections.append('@' + connection_name)
                if (len(connections) == limit):
                    break

            Path(path).mkdir(parents=True, exist_ok=True)


            with open(f'{path}//{username}_{len(connections)}.json', 'w') as file:
                json.dump(connections, file)

        else:
            connections = json.load(file)
            file.close()

        self.close_tab()
            
        return connections


    def get_user_from_post(self, url:str) -> str:
        self.driver.get(url)

        WebDriverWait(self.driver, self.timeout).until(
            lambda x: x.find_element_by_css_selector('article[role=\'presentation\'] a'))
        
        user = self.driver.find_element_by_css_selector('article[role=\'presentation\'] a') \
                                .get_attribute('href').split('/')[-2]
        return user


    def write_comment(self, comment:str):

        # Click Comment's Box
        self.driver \
            .find_element_by_css_selector('article[role=\'presentation\'] form > textarea') \
            .click()

        # Write in Comment's Box
        comment_box = self.driver \
                        .find_element_by_css_selector('article[role=\'presentation\'] form > textarea') \
                        .send_keys(comment)

    def override_post_requests_js(self, comment:str):
        '''
            This method was created because ChromeDriver doesn't support characters outside of BMP.
            Executed javascript code in Chrome's Browser to be able to post those emojis and characters

            Explanation: It overrides HTTP POST requests method in order to change the body (in this case the comment)
        '''

        
        self.driver.execute_script('''
            XMLHttpRequest.prototype.realSend = XMLHttpRequest.prototype.send;
            let re = RegExp('comment_text=.*&replied_to_comment_id=');

            var newSend = function(vData) {
                if (re.test(vData)) {
                    vData = 'comment_text=''' + comment + '''&replied_to_comment_id=';
                }

                this.realSend(vData); 
            };
            XMLHttpRequest.prototype.send = newSend;
        ''')
        

    def send_comment(self) -> bool:
        try:
            
            # Click Post's Button to send Comment
            self.driver \
                .find_element_by_css_selector('article[role=\'presentation\'] form > button') \
                .click()

        except WebDriverException:
            sleep(60) # Couldn't comment error pop up. No specific css selector. (<p> was too risky because of pop up's warnings such as cookies one)

        # Wait the loading icon disappear
        WebDriverWait(self.driver, self.timeout).until_not(
            lambda x: x.find_element_by_css_selector('article[role=\'presentation\'] form > div'))
        
        # Text in Comment's Box
        return not self.driver.find_element_by_css_selector('article[role=\'presentation\'] form > textarea').text

        
        
    def comment_post(self, url:str, expr:str, connections:List[str], get_interval:Callable[[], float]):
        expr_parts = re.split(r'(?<!\\)@', expr)
        n = len(expr_parts) - 1

        if self.driver.current_url != url:
            self.driver.get(url)
            
            WebDriverWait(self.driver, self.timeout).until(
            lambda x: x.find_element_by_css_selector('article[role=\'presentation\'] a'))
        
 
        def chunks() -> Iterator[str]: 
            for idx in range(0, (len(connections) // n) * n, n):  
                yield connections[idx:idx + n]

        comments = Comments(chunks(), expr_parts)


        for comment in comments.generate():
            success = False
            has_input = False

            while not success:
                
                if not has_input:
                    try:
                        self.write_comment(comment)
                        
                    except WebDriverException: # This would be pretty sure a char/emoji not in BMP because ChormeDriver doesn't support.
                            self.override_post_requests_js(comment)
                            comment = '''
                                    Info: Message is fine. If you open this post in another browser you can see it is working. Can\'t show here the real message because there are some characters not supported by ChromeDriver (non-BMP chars)
                                    '''
                            self.write_comment(comment)

                    has_input = True

            
                success = self.send_comment()
                sleep(get_interval())


    def close_driver(self):
        self.driver.close()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_driver()
