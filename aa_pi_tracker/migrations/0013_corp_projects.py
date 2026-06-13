from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("aa_pi_tracker", "0012_add_skill_trained_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="piowner",
            name="shared_with_corp",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="piproject",
            name="is_corp_project",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="piproject",
            name="corp_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="piproject",
            name="corp_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="piproject",
            name="participants",
            field=models.ManyToManyField(
                blank=True,
                related_name="corp_projects",
                to="aa_pi_tracker.piowner",
            ),
        ),
        migrations.AlterModelOptions(
            name="general",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": [
                    ("view_pi", "Can access PI Tracker"),
                    ("manage_corp_pi", "Can manage Corp PI Projects"),
                ],
            },
        ),
    ]
