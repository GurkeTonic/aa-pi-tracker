# Django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_pi_tracker", "0007_piowner_skills"),
    ]

    operations = [
        migrations.AddField(
            model_name="piplanet",
            name="user_resource",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
