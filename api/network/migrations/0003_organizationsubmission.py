# Generated for the public-resources directory intake (charity pivot).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('network', '0002_representative_accreditation_expiration_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organization_name', models.CharField(max_length=500)),
                ('contact_name', models.CharField(blank=True, max_length=255)),
                ('contact_email', models.EmailField(max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=64)),
                ('website', models.URLField(blank=True)),
                ('city', models.CharField(blank=True, max_length=255)),
                ('state', models.CharField(blank=True, max_length=64)),
                ('offers_pro_bono', models.BooleanField(default=False)),
                ('intent', models.CharField(choices=[('listing', 'Be listed as a public resource'), ('partner', 'Offer VisaNav to our clients (pilot partner)')], default='listing', max_length=32)),
                ('message', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=32)),
                ('reviewer_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
    ]
