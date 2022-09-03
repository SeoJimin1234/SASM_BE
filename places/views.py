from places.serializers import PlaceSerializer,PlaceDetailSerializer
from users.serializers import UserSerializer
from .models import Place, PlacePhoto, SNSType, SNSUrl
from users.models import User

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action

import os
import json
import requests
import pandas as pd
import boto3
from urllib import parse
# import geopandas as gpd
# from tqdm import tqdm
import haversine as hs
from haversine import Unit

# Create your views here.
aws_access_key_id = getattr(settings,'AWS_ACCESS_KEY_ID')
aws_secret_access_key = getattr(settings,'AWS_SECRET_ACCESS_KEY')
kakao_rest_api_key = getattr(settings, 'KAKAO_REST_API_KEY')
#google_rest_api_key = getattr(settings, 'GOOGLE')
def get_s3(place,num):
    s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key)
    obj_list = s3.list_objects(Bucket='sasm-bucket',Prefix='places/')
    content_list = obj_list['Contents']
    for content in content_list:
        if place+'_'+num in content['Key']:
            result = content['Key']
            break
    return result

def addr_to_lat_lon(addr):
    url = 'https://dapi.kakao.com/v2/local/search/address.json?query={address}'.format(address=addr)
    headers = {"Authorization": "KakaoAK " + kakao_rest_api_key}
    result = json.loads(str(requests.get(url, headers=headers).text))
    match_first = result['documents'][0]['address']
    x=float(match_first['x'])
    y=float(match_first['y'])
    return (x, y)

def save_place_db(request):
    df = pd.read_excel("SASM_DB.xlsx", engine="openpyxl")
    df = df.fillna('')
    for dbfram in df.itertuples():
        place_name = dbfram[1]
        print(place_name)
        url = get_s3(place_name, "대표사진")
        encode_url = parse.quote(url)
        obj = Place.objects.create(
            place_name=dbfram[1],
            category=dbfram[2],
            vegan_category=dbfram[3],
            tumblur_category=dbfram[4],
            reusable_con_category=dbfram[5],
            pet_category=dbfram[6],
            mon_hours=dbfram[7],
            tues_hours=dbfram[8],
            wed_hours=dbfram[9],
            thurs_hours=dbfram[10],
            fri_hours=dbfram[11],
            sat_hours=dbfram[12],
            sun_hours=dbfram[13],
            etc_hours=dbfram[14],
            place_review=dbfram[15],
            address=dbfram[16],
            right_coordinate=addr_to_lat_lon(dbfram[16])[0],
            left_coordinate=addr_to_lat_lon(dbfram[16])[1],
            short_cur=dbfram[17],
            phone_num=dbfram[18],
            rep_pic = 'https://sasm-bucket.s3.ap-northeast-2.amazonaws.com/{rep_url}'.format(rep_url=encode_url),
            )
        obj.save()
        id = obj.id
        for j in range(1,4):
            url = get_s3(place_name, str(j))
            encode_url = parse.quote(url)
            img = PlacePhoto.objects.create(
                image = 'https://sasm-bucket.s3.ap-northeast-2.amazonaws.com/{photo_url}'.format(photo_url=encode_url),
                place_id=id,
                )
            img.save()
        # k = 19
        # while(True):
        #     try:
        #         sns_type = dbfram[k]
        #         if SNSType.objects.filter(name=sns_type).exists():
        #             obj = SNSUrl.objects.create(
        #                 snstype=SNSType.objects.get(name=sns_type).id,
        #                 url = dbfram[k+1],
        #                 place_id=id,
        #             )
        #             obj.save()
        #         else:
        #             obj = SNSType.objects.create(
        #                 name = sns_type,
        #             )
        #             obj.save()
        #             obj = SNSUrl.objects.create(
        #                 snstype=SNSType.objects.get(name=sns_type).id,
        #                 url = dbfram[k+1],
        #                 place_id=id,
        #             )
        #             obj.save()
        #         k+=2
        #     except:
        #         break
    return JsonResponse({'msg': 'success'})

class BasicPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'

class PlaceListView(viewsets.ModelViewSet):
    '''
        place의 list의 정보를 주는 API
    '''
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes=[
        AllowAny,
    ]
    pagination_class=BasicPagination
    
    def post(self,request):
        left = request.data['left']
        right = request.data['right']
        my_location = (float(left), float(right))
        for place in self.queryset:
            place_location = (place.left_coordinate, place.right_coordinate)
            place.distance = hs.haversine(my_location, place_location)
            place.save()
        return Response(status=status.HTTP_200_OK)
        
    def get(self, request):
        qs = self.get_queryset().order_by('distance')
        
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_paginated_response(self.get_serializer(page, many=True).data) 
        else:
            serializer = self.get_serializer(page, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PlaceDetailView(viewsets.ModelViewSet):
    '''
        place의 detail 정보를 주는 API
    '''
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes=[
        AllowAny,
    ]
    def get(self,request,pk):
        place = Place.objects.get(id=pk)
        response = Response(PlaceDetailSerializer(place).data, status=status.HTTP_200_OK)
        return response

class PlaceLikeView(viewsets.ModelViewSet):
    serializer_class=PlaceSerializer
    queryset = Place.objects.all()
    permission_classes=[
        IsAuthenticated,
    ]
    def get(self,request,pk):
        place = get_object_or_404(Place, pk=pk)
        like_id = place.place_likeuser_set.all()
        users = User.objects.filter(id__in=like_id)
        serializer = UserSerializer(users, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        id = request.data['id']
        place = get_object_or_404(Place, pk=id)
        if request.user.is_authenticated:
            user = request.user
            profile = User.objects.get(email=user)
            check_like = place.place_likeuser_set.filter(pk=profile.pk)

            if check_like.exists():
                place.place_likeuser_set.remove(profile)
                place.place_like_cnt -= 1
                place.save()
                return Response(status.HTTP_204_NO_CONTENT)
            else:
                place.place_likeuser_set.add(profile)
                place.place_like_cnt += 1
                place.save()
                return Response(status.HTTP_201_CREATED)
        else:
            return Response(status.HTTP_204_NO_CONTENT)

class PlaceSearchView(viewsets.ModelViewSet):
    serializer_class=PlaceDetailSerializer
    queryset = Place.objects.all()
    permission_classes=[
        AllowAny,
    ]
    def post(self,request):
        searchword = request.data['search']
        search_list = Place.objects.filter(Q(place_name__icontains=searchword))
        print(search_list)
        serializer = self.get_serializer(search_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)