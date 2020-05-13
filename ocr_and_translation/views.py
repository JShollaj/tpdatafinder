from django.shortcuts import render,reverse,redirect
from django.http import HttpResponse,HttpResponseRedirect,JsonResponse
from django.core.files.storage import FileSystemStorage
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.viewsets import ModelViewSet

from celery.result import AsyncResult

from .serializers import SavedModelSerializer
from .models import SavedModel,InterSavedModel
from .step_1_greyX_TP import scrap_the_file
from .tasks import upload_via_celery

from pydrive.auth import GoogleAuth, AuthenticationError
from pydrive.drive import GoogleDrive
import pandas as pd
import json

# Create your views here.
input_path = settings.MEDIA_ROOT+'/screenshots/full/'
output_path = settings.MEDIA_ROOT+'/ocr/'

gauth = GoogleAuth()
@csrf_exempt
def login(request):
    return HttpResponseRedirect(gauth.GetAuthUrl())

def authorized_view(request):
    x = request.GET["code"]
    request.session["code"] = x
    gauth.Auth(x)
    return HttpResponseRedirect(reverse("upload_form"))

@csrf_exempt
def upload_form(request):
    if gauth.credentials is None:
        return HttpResponseRedirect(reverse("login"))


    return render(request,"form_.html")

@csrf_exempt
def uplo_custom(request):
    if gauth.credentials is None:
        return HttpResponseRedirect(reverse("login"))

    InterSavedModel.objects.all().delete()
    if request.method == "POST" and request.FILES:
        file = request.FILES["links"]
        # check = request.POST["check"] if "check" in request.POST else "off"
        check = "on"
        file_name = request.POST["csv_name"]

        if not (file.name.endswith(".csv") or file.name.endswith(".txt")):
            return render(request,"form_.html",context={"required":"File must be of type .txt or .csv"})

        fs = FileSystemStorage(location=settings.MEDIA_ROOT+"/uploaded")
        filename = fs.save(file.name, file)

        if check == "off":
            scrap_the_file(filename,gauth)
            all_objects_dict = {"web_address":[],"original_text":[],"translated_text":[],"name":[],"hyperlink":[],"img":[]}
            all_objects = InterSavedModel.objects.all()
            print(all_objects.__len__())
            for i in all_objects:
                all_objects_dict["web_address"].append(i.web_address)
                all_objects_dict["original_text"].append(i.original_text)
                all_objects_dict["translated_text"].append(i.translated_text)
                all_objects_dict["name"].append(i.link_name.replace("%20"," ").replace("%"," ").replace("/n", "").split(",")[1])
                all_objects_dict["hyperlink"].append("=HYPERLINK(file:///{})".format(i.link_name))

                all_objects_dict["img"].append([i.link_name])
                print([i.link_name])


            dataframe =  pd.DataFrame(all_objects_dict)
            dataframe.columns = ["Page","description","Translated Text","Name","hyperlink","img"]
            dataframe.to_csv(settings.MEDIA_ROOT+"/"+file_name+".csv")
        else:
            gauth.SaveCredentialsFile(credentials_file=settings.MEDIA_ROOT+"/file.txt")
            task = upload_via_celery.delay(filename,file_name)
            # while not task.ready():
            #     print(f'State={task.state}, info={task.info}, {task.ready()}')
            return HttpResponseRedirect(reverse("get_task_progress",args=(task.task_id,)))

            # return render(request, 'display_progress.html', context={'task_id': task.task_id})

    elif request.method == "POST" and not request.FILES:
        if "typed_urls" not in request.POST:
            return render(request,"form_.html",{"required":"Please type urls"})
        elif request.POST["typed_urls"] == "":
            return render(request,"form_.html",{"required":"Please type urls"})

        url_list = str(request.POST["typed_urls"]).split(";")
        url_list = url_list[:-1]
        # check = request.POST["check"] if "check" in request.POST else "off"
        check = "on"
        file_name = request.POST["csv_name"]

        if check == "off":
            scrap_the_file(url_list,gauth)
            all_objects_dict = {"web_address":[],"original_text":[],"translated_text":[],"name":[],"hyperlink":[],"img":[],"link_to_image":[]}
            all_objects = InterSavedModel.objects.all()
            print(all_objects.__len__())
            for i in all_objects:
                all_objects_dict["web_address"].append(i.web_address)
                all_objects_dict["original_text"].append(i.original_text)
                all_objects_dict["translated_text"].append(i.translated_text)
                all_objects_dict["name"].append(i.link_name.replace("%20"," ").replace("%"," ").replace("/n", "").split(",")[1])
                all_objects_dict["hyperlink"].append("=HYPERLINK(file:///{})".format(i.link_name))

                all_objects_dict["img"].append([i.link_name])


                all_objects_dict["link_to_image"].append([i.image])

                print([i.image])


            dataframe =  pd.DataFrame(all_objects_dict)
            dataframe.columns = ["Page","description","Translated Text","Name","hyperlink","img"]
            dataframe.to_csv(settings.MEDIA_ROOT+"/"+file_name+".csv")

        else:
            gauth.SaveCredentialsFile(credentials_file=settings.MEDIA_ROOT+"/file.txt")
            task = upload_via_celery.delay(url_list,file_name)

            return HttpResponseRedirect(reverse("get_task_progress",args=(task.task_id,)))


    return HttpResponseRedirect(reverse("upload_form"))

def get_task_progress(request,task_id):
    return render(request, 'display_progress.html', context={'task_id': task_id})

def get_task_update(request,task_id):
    result = AsyncResult(task_id)
    if result.state == "SUCCESS":
        return JsonResponse({"state":result.state,"info":result.info,"file_name":result.get()})
    return JsonResponse({"state":result.state,"info":result.info})

def get_table(request,file_name):
    df = pd.read_csv(settings.MEDIA_ROOT+"/"+file_name+".csv")
    # print(list(df["link_to_image"]))
    data = json.dumps({"links":list(df["link_to_image"]),"drive_links":list(df["drive_link"])})

    df.drop(columns = ["link_to_image","drive_link"],inplace = True)
    print(df.columns)

    return render(request,"table.html",{"table":df,"links":str(data)})

    return HttpResponse(df.to_html())
class SavedModelViewSet(ModelViewSet):
    serializer_class = SavedModelSerializer
    queryset = SavedModel.objects.all()
