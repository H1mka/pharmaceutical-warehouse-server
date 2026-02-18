from django.shortcuts import render
from django.http import HttpResponse
from .models import Product
import datetime

# Create your views here.
def home (request):
  return HttpResponse('Home url')

def create_product(request):
  return HttpResponse('Created')
