from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("aa_pi_tracker", "0006_pistorageitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="piowner",
            name="interplanetary_consolidation",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="piowner",
            name="command_center_upgrades",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
