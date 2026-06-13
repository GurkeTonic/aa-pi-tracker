from django.db import models


class PiMarketPrice(models.Model):
    type_id = models.IntegerField(unique=True)
    type_name = models.CharField(max_length=100)
    tier = models.IntegerField(default=0)  # 0=P0 raw, 1=P1, 2=P2, 3=P3, 4=P4
    jita_buy = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tier", "type_name"]

    def __str__(self):
        return f"{self.type_name} ({self.jita_buy:,.0f} ISK)"
