# Django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_pi_tracker", "0011_add_skill_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="piowner",
            name="interplanetary_consolidation_trained",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="piowner",
            name="command_center_upgrades_trained",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="piowner",
            name="planetology_trained",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="piowner",
            name="advanced_planetology_trained",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="piowner",
            name="remote_sensing_trained",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
