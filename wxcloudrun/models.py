from django.db import models


class Counters(models.Model):
    count = models.IntegerField(default=0)

    class Meta:
        db_table = "Counters"
