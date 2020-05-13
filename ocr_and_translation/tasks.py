# from celery import app
from django.conf import settings
from .step_1_greyX_TP import scrap_the_file
from pydrive.auth import GoogleAuth
from . import views
import os
import pandas as pd
from .models import InterSavedModel
from django_gui.celery import app

@app.task(bind=True)
def upload_via_celery(self,name,file_name):
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(settings.MEDIA_ROOT+"/file.txt")

    scrap_the_file(name,gauth,self)
    all_objects_dict = {"web_address":[],"original_text":[],"translated_text":[],"name":[],"hyperlink":[],"img":[],"link_to_image":[],"drive_link":[]}
    all_objects = InterSavedModel.objects.all()
    print(all_objects.__len__())
    for i in all_objects:
        all_objects_dict["web_address"].append(i.web_address)
        all_objects_dict["original_text"].append(i.original_text)
        all_objects_dict["translated_text"].append(i.translated_text)
        all_objects_dict["name"].append(i.link_name.replace("%20"," ").replace("%"," ").replace("/n", ""))
        all_objects_dict["hyperlink"].append("=HYPERLINK(file:///{})".format(i.link_name))

        all_objects_dict["img"].append(i.link_name)
        all_objects_dict["link_to_image"].append(i.image)
        all_objects_dict["drive_link"].append(i.link)

    dataframe =  pd.DataFrame(all_objects_dict)
    dataframe.columns = ["Page","description","Translated Text","Name","hyperlink","img","link_to_image","drive_link"]
    dataframe.to_csv(settings.MEDIA_ROOT+"/"+file_name+".csv")

    return file_name
