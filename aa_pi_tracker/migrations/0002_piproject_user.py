# Django
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_owner_to_user(apps, schema_editor):
    PiProject = apps.get_model("aa_pi_tracker", "PiProject")
    for project in PiProject.objects.select_related("owner__user").all():
        project.user_id = project.owner.user_id
        project.save(update_fields=["user_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("aa_pi_tracker", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="piproject",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pi_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(migrate_owner_to_user, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="piproject",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pi_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RemoveField(model_name="piproject", name="owner"),
    ]
