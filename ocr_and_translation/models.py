from django.db import models
from django.conf import settings
# Create your models here.



class SavedModel(models.Model):
    web_address = models.CharField(max_length=100)
    original_text = models.CharField(max_length=10000)
    translated_text = models.CharField(max_length=10000)
    link_name = models.CharField(max_length=1000,default=".png")
    link = models.URLField()

class InterSavedModel(models.Model):
    web_address = models.CharField(max_length=100)
    original_text = models.CharField(max_length=10000)
    translated_text = models.CharField(max_length=10000)
    link_name = models.CharField(max_length=1000,default=".png")
    # image = models.ImageField(upload_to="media/screenshots/permanent/")
    image = models.URLField()
    link = models.URLField()
