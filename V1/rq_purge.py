import random
from rq_helper import RedisQueueManager
from datetime import datetime
from zoneinfo import ZoneInfo 
import uuid
import json

Redis_Queue = RedisQueueManager()

Redis_Queue.purge()
