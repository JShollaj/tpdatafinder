from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import urllib
import time
import sys
import traceback
import re
from django.conf import settings
import os
import html5lib
from googletrans import Translator
from pydrive.drive import GoogleDrive
from .step_2_ocr import main
import platform
from django.utils import timezone
import re

from .models import SavedModel,InterSavedModel

exts = [".txt",".pdf",".jpg",".jpeg",".gif",".png",".bmp",".avi",".mov", ".doc",".docx",".xls",".xlsx",".ppt",".pptx",".mp4",".mp3",".wav",".flac",".ogg",".mkv"]

class scraper:
    def __init__(self, driver, base_url):
        self.history = []
        self.driver = driver
        set_width = 2700
        set_height = 2000
        self.base_url = base_url
        self.driver.set_window_size(set_width, set_height)

        self.directory = settings.MEDIA_ROOT+'/screenshots/'
        self.full = settings.MEDIA_ROOT+'/screenshots/full/'
        self.permanent = settings.MEDIA_ROOT+'/screenshots/permanent/'

        self.tmp = settings.MEDIA_ROOT+'/screenshots/tmp/'
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
            os.makedirs(self.full)
            os.makedirs(self.tmp)
        else:
            if not os.path.exists(self.full):
                os.makedirs(self.full)
            if not os.path.exists(self.tmp):
                os.makedirs(self.tmp)


    def start(self, url,gauth,task,pr,a):
        isOurAbsOrRelAndNotCss = lambda x: ("http" not in x or self.base_url in x) and '#' not in x
        try:
            #skip any that are already not our base domain
            print("STARTED...")
            if isOurAbsOrRelAndNotCss(url):
                print("ABOUT TO GET...  {}".format(url))
                self.driver.get(url)
                task.update_state(state='PROGRESS', meta={'done': pr, 'total': a,'url':url})

                print("GOT...")
                #allow time to load page before determining dimensions
                time.sleep(3)
                #check again in case we got a redirect, check if its an rss page, check if its a media extension
                if isOurAbsOrRelAndNotCss(self.driver.current_url) and "rss xmlns:atom" not in self.driver.page_source and not any([(ext in url) for ext in exts]):
                    scrapedUrls = self.parseUrls()
                    #limit filename length
                    # print("SAVED:",url)
                    self.saveImage(self.driver.title[:100] + ".png",url,gauth)
                    for scrapedUrl in scrapedUrls:
                        #its a relative link, lets re add the base url
                        if "http" not in scrapedUrl:
                            scrapedUrl = self.base_url + scrapedUrl
                        if scrapedUrl not in self.history:
                            self.history.append(scrapedUrl)
                            self.history.append(scrapedUrl+"/")
                            self.history.append(scrapedUrl+"#")

                            self.start(scrapedUrl,gauth,task,pr,a)
        except WebDriverException:
            print(f"Failed processing:{'url'}")

    def parseUrls(self):
        urls = BeautifulSoup(self.driver.page_source,"html5lib").findAll('a', href=True, limit=8)
        #check to make sure we are in right domain if it is absolute, or it is relative
        return [url["href"] for url in urls ]

    def saveImage(self, filename,url,gauth):
        yDelta, xDelta, fullWidth, fullHeight, windowHeight = self.getDimensions()
        self.triggerAnimations(fullHeight)
        images = self.processImages(yDelta, xDelta, fullWidth, fullHeight, windowHeight)
        self.stitchScreenshots(images, fullWidth, fullHeight, filename,url,gauth)
        self.clear_tmp()

    def triggerAnimations(self, fullHeight):
        #scroll down the page by the height of the window
        for i in range(0, fullHeight, 800):
            self.driver.execute_script("window.scrollTo(%s,%s)" % (0,i))
            time.sleep(1)

    def getDimensions(self):
        widths = self.driver.execute_script(
            "return widths = [document.documentElement.clientWidth, document.body ? document.body.scrollWidth : 0, document.documentElement.scrollWidth, document.body ? document.body.offsetWidth : 0, document.documentElement.offsetWidth ]")
        heights = self.driver.execute_script(
            "return heights = [document.documentElement.clientHeight, document.body ? document.body.scrollHeight : 0, document.documentElement.scrollHeight, document.body ? document.body.offsetHeight : 0, document.documentElement.offsetHeight]")
        fullWidth = max(widths)
        fullHeight = max(heights)
        windowWidth = self.driver.execute_script("return window.innerWidth")
        windowHeight = self.driver.execute_script("return window.innerHeight")
        return windowHeight, windowWidth, fullWidth, fullHeight, windowHeight

    def processImages(self, yDelta, xDelta, fullWidth, fullHeight, windowHeight):
        images = []
        #Disable all scrollbars when taking the screenshots
        self.driver.execute_script("document.body.style.overflowY = 'hidden';")
        yPos = 0
        while yPos <= fullHeight:
            self.driver.execute_script("window.scrollTo(%s,%s)" % (0, yPos))
            time.sleep(1)
            filename = ((self.tmp+"screenshot_%s.png") % yPos)
            images.append(filename)
            self.driver.get_screenshot_as_file(filename)
            yPos += yDelta
            #if another full window would take us out of the page
            remainder = fullHeight - yPos
            if yPos + yDelta > fullHeight and remainder > 0:
                #scroll to bottom, take a shot, crop it
                self.driver.execute_script("window.scrollTo(%s,%s)" % (0, fullHeight))
                filename = ((self.tmp+"screenshot_%s_temp.png") % yPos)
                self.driver.get_screenshot_as_file(filename)
                base = Image.open(filename)
                #crop is measured from top left
                cropped = base.crop((0, windowHeight - remainder, fullWidth, windowHeight))
                filename = ((self.tmp+"screenshot_%s_temp.png") % yPos)
                cropped.save(filename)
                images.append(filename)
                base.close()
        return images

    def stitchScreenshots(self, images, total_width, total_height, filename,url,gauth):
        stitched_image = Image.new('RGB', (total_width, total_height))
        y_offset = 0
        for im in images:
            im = Image.open(im)
            kos = self.base_url.replace("/", "X")
            stitched_image.paste(im, (0, y_offset))
            y_offset += im.size[1]
        print(stitched_image.size)
        fname = urllib.parse.quote(filename).replace("/","")
        stitched_image.save(f"{self.full}/_{kos}{fname}")

        stitched_image = stitched_image.resize((100,100))
        per_name = re.sub('[\W_]+', '', str(timezone.now()))+".jpg"
        stitched_image.save(f"{self.permanent}/{per_name}")

        #Save image file to drive.
        name = f"_{kos}{fname}"
        # name = name.replace("%20"," ").replace("%"," ").replace("/n", "").split(",")[1]
        # print(name)

        drive = GoogleDrive(gauth)
        list_ = ListFolder("root",drive)
        file = drive.CreateFile({'parents': [{"id" : list_["full_screenshots"]}]})
        file.SetContentFile(f"{self.full}/_{kos}{fname}")
        file["title"] = url.replace("/", "X")
        file.Upload()
        original = main(f"{self.full}/_{kos}{fname}")

        translator = Translator()
        translated = translator.translate(original, dest='en') if original is not None else " "

        saved = SavedModel()
        inter_saved = InterSavedModel()
        #Save web_address, original_text, translated_text, and drive link to image into table
        saved.web_address = self.base_url
        saved.original_text = original

        try:
            saved.translated_text = translated.text
        except:
            saved.translated_text = " "
        saved.link = file.metadata["embedLink"]
        # saved.link = f'{kos},{fname}'
        saved.link_name = name
        saved.save()

        inter_saved.web_address = self.base_url
        inter_saved.original_text = original
        inter_saved.translated_text = translated.text
        inter_saved.link = file.metadata["embedLink"]
        # saved.link = f'{kos},{fname}'
        inter_saved.link_name = name
        inter_saved.image = "media/screenshots/permanent/"+per_name
        inter_saved.save()

        stitched_image.close()

        return filename

    def clear_tmp(self):
        dirPath = self.tmp
        fileList = os.listdir(dirPath)
        for fileName in fileList:
            os.remove(dirPath+"/"+fileName)


def clear_full():
    dirPath = settings.MEDIA_ROOT+'/screenshots/full/'
    fileList = os.listdir(dirPath)
    for fileName in fileList:
        os.remove(dirPath+"/"+fileName)


def scrap_the_file(name,gauth,task):

    pr = 0
    if type(name) == str:
        f = open(settings.MEDIA_ROOT+"/uploaded/"+name, 'r')
        a = f.read()

        # for i in ["https://www.devatus.fi"]:
        task.update_state(state='PROGRESS', meta={'done': 0, 'total': len(a.splitlines())})
        for i in a.splitlines():
            if "http" not in i:
                i = "https://"+i
            url = (i)
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            if platform.system()=="Darwin":
                driver = webdriver.Chrome("chromedriver",options=options)
            elif platform.system() =="Windows":
                driver = webdriver.Chrome(settings.EXECUTABLE_ROOT+"/chromedriver_win.exe",options=options)
            else:
                driver = webdriver.Chrome("chromedriver",options=options)

            try:
                print("ABOUT TO GET STARTED...")
                w = scraper(driver, url)
                w.start(url,gauth,task,pr,len(a.splitlines()))
                w.clear_tmp()
            except Exception as exc:
                print(exc)
                traceback.print_exc(file=sys.stdout)
            driver.quit()
            pr+=1
            task.update_state(state='PROGRESS', meta={'done': pr, 'total': len(a.splitlines())})
            # print(task.state,task.value)
        clear_full()

    else:

        for i in name:
            if "http" not in i:
                i = "https://"+i
            url = (i)
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            if platform.system()=="Darwin":
                driver = webdriver.Chrome("chromedriver",options=options)
            elif platform.system() =="Windows":
                driver = webdriver.Chrome(settings.EXECUTABLE_ROOT+"/chromedriver_win.exe",options=options)
            else:
                driver = webdriver.Chrome("chromedriver",options=options)

            try:
                print("ABOUT TO GET STARTED...")
                w = scraper(driver, url)
                w.start(url,gauth,task,pr,len(name))
                w.clear_tmp()
            except Exception as exc:
                print(exc)
                traceback.print_exc(file=sys.stdout)
            driver.quit()
        clear_full()




def ListFolder(parent,drive):
  filelist={}
  file_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % parent}).GetList()
  for f in file_list:
      if f['mimeType']=='application/vnd.google-apps.folder' and f['title']=="full_screenshots":
          filelist[f["title"]]=f["id"]

  return filelist
