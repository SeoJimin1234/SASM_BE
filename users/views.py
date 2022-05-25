from rest_framework.response import Response 
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView
from rest_framework import status
from .models import User
from .serializers import *
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
import urllib
from django.conf import settings
from allauth.socialaccount.models import SocialAccount
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google import views as google_view
from allauth.socialaccount.providers.kakao import views as kakao_view
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from django.http import JsonResponse
import requests
from json.decoder import JSONDecodeError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import string
import random

state = getattr(settings, 'STATE')
STATE_LENGTH = 15
string_pool = string.ascii_letters + string.digits
for i in range(STATE_LENGTH):
    state += random.choice(string_pool)

BASE_URL = 'http://127.0.0.1:8000/'
GOOGLE_CALLBACK_URI = BASE_URL + 'users/google/callback/'
KAKAO_CALLBACK_URI = BASE_URL + 'users/kakao/callback/'
NAVER_CALLBACK_URI = BASE_URL + 'users/naver/callback/'

#email 인증 관련
from django.utils.encoding import force_str
from rest_framework_jwt.settings import api_settings
from django.utils.http import urlsafe_base64_decode
import traceback
jwt_decode_handler= api_settings.JWT_DECODE_HANDLER
jwt_payload_get_user_id_handler = api_settings.JWT_PAYLOAD_GET_USER_ID_HANDLER

# 함수도 되고 클래스로도 만들 수 있음
class SignupView(CreateAPIView):
    model = get_user_model()
    serializer_class = UserSerializer
    permission_classes = [
        AllowAny, #AllowAny - 회원가입할 때는 절대 로그인이 될 수 없는 상황이니까 (아무나 접근 가능)
    ]
            
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def user_detail(request, pk):
    try:
        user = User.objects.get(pk=pk)
        return Response(UserSerializer(user).data)
    except User.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def Login(request):
    if request.method == 'POST':
        serializer = UserLoginSerializer(data=request.data)

        if not serializer.is_valid(raise_exception=True):
            return Response({"message": "Request Body Error"}, status=status.HTTP_409_CONFLICT)
        if serializer.validated_data['email'] == "None":
            return Response({"message": 'fail'}, status=status.HTTP_200_OK)
        response = {
            'success': True,
            'token': serializer.data['token']
        }
        return Response(response, status=status.HTTP_200_OK)

# 코드 요청
@method_decorator(csrf_exempt)
def kakao_login(request):
    rest_api_key = getattr(settings, 'KAKAO_REST_API_KEY')
    return redirect(
        f"https://kauth.kakao.com/oauth/authorize?client_id={rest_api_key}&redirect_uri={KAKAO_CALLBACK_URI}&response_type=code"
    )

# 토큰 요청
@method_decorator(csrf_exempt)
def kakao_callback(request):
    rest_api_key = getattr(settings, 'KAKAO_REST_API_KEY')
    code = request.GET.get("code")
    redirect_uri = KAKAO_CALLBACK_URI
    
    token_req = requests.get(
        f"https://kauth.kakao.com/oauth/token?grant_type=authorization_code&client_id={rest_api_key}&redirect_uri={redirect_uri}&code={code}"
    )
    token_req_json = token_req.json()
    error = token_req_json.get("error")
    if error is not None:
        raise JSONDecodeError(error)
    access_token = token_req_json.get("access_token")

    profile_request = requests.get('https://kapi.kakao.com/v2/user/me', headers={"Authorization": f'Bearer ${access_token}'})

    profile_json = profile_request.json()

    kakao_account = profile_json.get('kakao_account')

    # 이메일 외에도 프로필 이미지, 배경 이미지 url 등 가져올 수 있음
    
    email = kakao_account.get('email', None)
    if email is None:
        print("email None")
    try:
        user = User.objects.get(email=email)
        social_user = SocialAccount.objects.get(user=user)
        if social_user is None:
            return JsonResponse(
                {'err_msg': 'email exists but not social user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if social_user.provider != 'kakao':
            return JsonResponse(
                {'err_msg': 'no matching social type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}users/kakao/login/finish", data=data
        )
        accept_status = accept.status_code
        if accept_status != 200:
            return JsonResponse(
                {'err_msg': 'failed to signin'},
                status=accept_status
            )
        accept_json = accept.json()
        accept_json.pop('user', None)
        return JsonResponse(accept_json)
    except User.DoesNotExist:
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}users/kakao/login/finish/", data=data
        )
        accept_status = accept.status_code
        if accept_status != 200:
            return JsonResponse(
                {'err_msg': 'failed to signup'},
                status=accept_status
            )
        accept_json = accept.json()
        accept_json.pop('user', None)
        return JsonResponse(accept_json)

@method_decorator(csrf_exempt, name='dispatch')
class KakaoLogin(SocialLoginView):
    adapter_class = kakao_view.KakaoOAuth2Adapter
    client_class = OAuth2Client
    callback_url = KAKAO_CALLBACK_URI

def google_login(request):
    scope = "https://www.googleapis.com/auth/userinfo.email"
    client_id = getattr(settings, "SOCIAL_AUTH_GOOGLE_CLIENT_ID")
    return redirect(
        f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&response_type=code&redirect_uri={GOOGLE_CALLBACK_URI}&scope={scope}"
    )

def google_callback(request):
    client_id = getattr(settings, "SOCIAL_AUTH_GOOGLE_CLIENT_ID")
    client_secret = getattr(settings, "SOCIAL_AUTH_GOOGLE_SECRET")
    code = request.GET.get('code')

    token_req = requests.post(
        f"https://oauth2.googleapis.com/token?client_id={client_id}&client_secret={client_secret}&code={code}&grant_type=authorization_code&redirect_uri={GOOGLE_CALLBACK_URI}&state={state}"
    )

    token_req_json = token_req.json()
    error = token_req_json.get("error")
    if error is not None:
        raise JSONDecodeError(error)
    access_token = token_req_json.get('access_token')

    email_req = requests.get(
        f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
    )
    email_req_status = email_req.status_code
    
    if email_req_status != 200:
        return JsonResponse(
            {'err_msg': 'failed to get email'},
            status=status.HTTP_400_BAD_REQUEST
        )
    email_req_json = email_req.json()
    email = email_req_json.get('email')

    try:
        user = User.objects.get(email=email)    
        if user is None:
            print("user")    
        social_user = SocialAccount.objects.get(user=user)
        
        if social_user is None:
            return JsonResponse(
                {'err_msg': 'email exists but not social user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if social_user.provider != 'google':
            return JsonResponse(
                {'err_msg': 'no matching social type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}users/google/login/finish/", data=data
        )
        accept_status = accept.status_code
       
        if accept_status != 200:
            return JsonResponse(
                {'err_msg': 'failed to signin'},
                status=accept_status
            )
        accept_json = accept.json()
        accept_json.pop('user', None)

        return JsonResponse(accept_json)
    except User.DoesNotExist:

        data = {'access_token': access_token, 'code': code}
        
        accept = requests.post(
            f"{BASE_URL}users/google/login/finish/", data=data
        )
        accept_status = accept.status_code
       
        if accept_status != 200:
            return JsonResponse(
                {'err_msg': 'failed to signup'},
                status=accept_status
            )
        accept_json = accept.json()
        accept_json.pop('user', None)
        return JsonResponse(accept_json)

class GoogleLogin(SocialLoginView):
    adapter_class = google_view.GoogleOAuth2Adapter
    callback_url = GOOGLE_CALLBACK_URI
    client_class = OAuth2Client

#def naver_login(request):
#    client_id = getattr(settings, "NAVER_CLIENT_ID")
#    return redirect(
#       f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={client_id}&state={state}&redirect_uri={NAVER_CALLBACK_URI}"
#    )
#
#def naver_callback(request):
#    client_id = getattr(settings, 'NAVER_CLIENT_ID')
#    client_secret = getattr(settings, "NAVER_SECRET_KEY")
#    code = request.GET.get("code")
#    
#    token_req = requests.get(
#        f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={client_id}&client_secret={client_secret}&code={code}&state={state}"
#    )
#
#    token_req_json = token_req.json()
#    error = token_req_json.get("error")
#    if error is not None:
#        raise JSONDecodeError(error)
#    access_token = token_req_json.get("access_token")
#
#    profile_request = requests.get('https://openapi.naver.com/v1/nid/me', headers={"Authorization": f'Bearer ${access_token}'})
#
#    profile_json = profile_request.json()
#
#    naver_account = profile_json.get('kakao_account')

class UserActivateView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, uid, token):
        try:
            real_uid = force_str(urlsafe_base64_decode(uid))
            print(real_uid)
            user = User.objects.get(pk=real_uid)
            if user is not None:
                payload = jwt_decode_handler(token)
                user_id =jwt_payload_get_user_id_handler(payload)
                print(type(user))
                print(type(user_id))
                if int(real_uid) == int(user_id):
                    user.is_active = True
                    user.save()
                    return Response(user.email + '계정이 활성화 되었습니다', status=status.HTTP_200_OK)
                return Response('인증에 실패하였습니다', status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response('인증에 실패하였습니다', status=status.HTTP_400_BAD_REQUEST)

        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
            print(traceback.format_exc())
            return Response('인증에 실패하였습니다',status=status.HTTP_400_BAD_REQUEST)
