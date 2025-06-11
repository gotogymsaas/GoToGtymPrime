from django.db import models


class NetPromoterScore(models.Model):
    score = models.IntegerField(
        choices=[(i, str(i)) for i in range(0, 11)],  # NPS scores range from 0 to 10
        help_text="NPS score provided by the respondent (0-10).",
    )
    date = models.DateField()

    def __str__(self):
        return f"NPS Score: {self.score} on {self.date}"