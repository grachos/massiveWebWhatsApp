from gevent import monkey
monkey.patch_all()

import time
import urllib.parse
import os
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='gevent')

# Global logic for the bot
bot_instance = None
bot_thread = None
stop_flag = False

# Constants
LOGIN_TIMEOUT = 120
PAGE_LOAD_TIMEOUT = 30
MESSAGE_DELAY = 10

class WhatsAppSender:
    def __init__(self, socket):
        self.driver = None
        self.wait = None
        self.socket = socket

    def log(self, message, type='info'):
        """Send a log message to the frontend."""
        self.socket.emit('log', {'message': message, 'type': type})
        print(f"[{type.upper()}] {message}")

    def setup_driver(self):
        """Initializes the Chrome WebDriver."""
        self.log("Setting up WebDriver...", "info")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--log-level=3")

        try:
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 20)
        except WebDriverException as e:
            self.log(f"Failed to initialize driver: {e}", "error")
            raise

    def wait_for_login(self):
        """Waits for login."""
        self.log("Opening WhatsApp Web...", "info")
        self.driver.get("https://web.whatsapp.com")

        self.log(f"Please scan the QR code within {LOGIN_TIMEOUT} seconds...", "warning")
        try:
            WebDriverWait(self.driver, LOGIN_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, "side"))
            )
            self.log("Login detected! Proceeding...", "success")
        except TimeoutException:
            self.log("Login timed out.", "error")
            raise Exception("Login Timeout")

    def send_messages(self, numbers, message):
        """Sends messages to the list of numbers."""
        encoded_message = urllib.parse.quote(message)
        success_count = 0
        fail_count = 0
        total = len(numbers)

        for index, number in enumerate(numbers):
            global stop_flag
            if stop_flag:
                self.log("Process stopped by user.", "warning")
                break

            self.log(f"Processing {index + 1}/{total}: {number}", "info")
            
            # Basic validation
            if not number.isdigit() or len(number) < 7:
                self.log(f"Skipping invalid format: {number}", "warning")
                fail_count += 1
                continue

            url = f"https://web.whatsapp.com/send?phone={number}&text={encoded_message}"
            
            try:
                self.driver.get(url)
                
                # Check for invalid number or send button
                try:
                    WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT).until(
                        EC.any_of(
                            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Send']")),
                            EC.element_to_be_clickable((By.XPATH, "//span[@data-icon='send']")),
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'url is invalid')]")),
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Phone number shared via url is invalid')]"))
                        )
                    )
                except TimeoutException:
                    self.log(f"Timeout loading chat for {number}.", "error")
                    fail_count += 1
                    continue

                # Check for invalid popup
                invalid_popups = self.driver.find_elements(By.XPATH, "//div[contains(text(), 'url is invalid')]") or \
                                 self.driver.find_elements(By.XPATH, "//div[contains(text(), 'Phone number shared via url is invalid')]")
                
                if invalid_popups:
                    self.log(f"WhatsApp says {number} is invalid.", "error")
                    fail_count += 1
                    # Close popup if possible or just continue (the navigate will reset)
                    continue

                # Should be valid
                send_btn = self.driver.find_element(By.XPATH, "//button[@aria-label='Send'] | //span[@data-icon='send']")
                send_btn.click()
                
                time.sleep(2) # Wait for send
                self.log(f"Message sent to {number}!", "success")
                success_count += 1

                # Throttle
                time.sleep(MESSAGE_DELAY)

            except Exception as e:
                self.log(f"Failed to send to {number}. Error: {str(e)}", "error")
                fail_count += 1

        self.log(f"Finished. Successful: {success_count}, Failed: {fail_count}", "success")
        self.socket.emit('finished')

    def teardown(self):
        if self.driver:
            self.log("Closing browser...", "info")
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

def run_bot(numbers, message):
    global bot_instance, stop_flag
    stop_flag = False
    
    bot_instance = WhatsAppSender(socketio)
    try:
        bot_instance.setup_driver()
        bot_instance.wait_for_login()
        bot_instance.send_messages(numbers, message)
    except Exception as e:
        socketio.emit('log', {'message': f"Critical Error: {str(e)}", 'type': 'error'})
    finally:
        if bot_instance:
            bot_instance.teardown()
            bot_instance = None

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_sending')
def handle_start(data):
    global bot_thread, bot_instance
    if bot_instance:
        emit('log', {'message': 'Bot is already running!', 'type': 'warning'})
        return

    numbers_text = data.get('numbers', '')
    message = data.get('message', '')
    
    numbers = [line.strip() for line in numbers_text.split('\n') if line.strip()]
    if not numbers:
        emit('log', {'message': 'No numbers provided.', 'type': 'error'})
        return
    if not message:
        emit('log', {'message': 'No message provided.', 'type': 'error'})
        return

    emit('log', {'message': 'Starting bot process...', 'type': 'info'})
    emit('log', {'message': 'Starting bot process...', 'type': 'info'})
    bot_thread = socketio.start_background_task(run_bot, numbers, message)

@socketio.on('stop_sending')
def handle_stop():
    global stop_flag
    stop_flag = True
    emit('log', {'message': 'Stop signal received. Stopping after current message...', 'type': 'warning'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
