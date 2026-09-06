from django.db import migrations
from django.utils.dateparse import parse_datetime


USERS = [
    {
        "email": "eviana67@gmail.com",
        "username": "eviana67@gmail.com",
        "first_name": "Eric",
        "last_name": "Viana Buendia",
        "age": 58,
        "password": "pbkdf2_sha256$1200000$yyKjKqTOjUjTWx7E6PMXtz$pDdWYP02W5URLocLyr3rwxop/LgGwoAkfvd0lYYrqdU=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-07-01 01:39:35.079412+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": False,
        "date_joined": "2026-07-01 01:39:35.080163+00:00",
        "last_login": "2026-09-06 20:45:30.527374+00:00",
    },
    {
        "email": "nepojim@gmail.com",
        "username": "nepojim@gmail.com",
        "first_name": "Nepomuceno",
        "last_name": "Jimenez",
        "age": 45,
        "password": "pbkdf2_sha256$1200000$xFCAdBEtazKHBfPQzdrhXo$gbT8XlTbRQC2AqonXRGwhrKKirrGkKnQoJfdzgUZEck=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-07-12 19:27:28.612581+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": True,
        "date_joined": "2026-07-12 19:27:28.613596+00:00",
        "last_login": "2026-07-12 19:28:39.427191+00:00",
    },
    {
        "email": "aemo@gmail.com",
        "username": "aemo@gmail.com",
        "first_name": "Andrea",
        "last_name": "Martinez Orozco",
        "age": 34,
        "password": "pbkdf2_sha256$1200000$IfsTuPkJmzSyxwPmC2gxWv$ZxqpZKlGKPbSLQ+VuYPDebNFb+LvHtx2b/mKtHQ7VVQ=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-07-17 22:32:29.433760+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": True,
        "date_joined": "2026-07-17 22:32:29.434517+00:00",
        "last_login": "2026-07-17 22:32:53.168449+00:00",
    },
    {
        "email": "shakimeb@hotmail.com",
        "username": "shakimeb@hotmail.com",
        "first_name": "Shakira",
        "last_name": "Mebarak",
        "age": 47,
        "password": "pbkdf2_sha256$1200000$AaW5pa0zdEnlthnKL6IcSe$n26JOfpFR4FZBQnY2Vhfq7bK064xxZVBojvNSJ2MnGs=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-07-18 00:13:29.187264+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": False,
        "date_joined": "2026-07-18 00:13:29.187677+00:00",
        "last_login": "2026-07-18 00:15:28.793084+00:00",
    },
    {
        "email": "hdelacalle@yahoo.es",
        "username": "hdelacalle@yahoo.es",
        "first_name": "Humberto",
        "last_name": "De la Calle",
        "age": 65,
        "password": "pbkdf2_sha256$1200000$NqL4ObOHnwuvCRnlo6SMKq$161lrWGQiflkfH8yLy+PWxjwTCTEk7PLeQ0dr9+dvtg=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-09-02 12:02:47.310307+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": True,
        "es_influencer": False,
        "date_joined": "2026-09-02 12:02:47.313040+00:00",
        "last_login": "2026-09-02 12:04:29.027069+00:00",
    },
    {
        "email": "lenchobojote@gmail.com",
        "username": "lenchobojote@gmail.com",
        "first_name": "lencho",
        "last_name": "de las mercedes",
        "age": 60,
        "password": "pbkdf2_sha256$1200000$NY29h5cqcVo1LkrnjzSU8J$LBh1Y3akiNPEEwf+j6eD9VcLq149W26WnDuwJ93vmI4=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-09-02 12:35:35.204091+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": True,
        "date_joined": "2026-09-02 12:35:35.204313+00:00",
        "last_login": "2026-09-02 18:10:47.550125+00:00",
    },
    {
        "email": "andreamarias@hotmail.com",
        "username": "adreamar@hotmail.com",
        "first_name": "Andrea",
        "last_name": "Martinez",
        "age": 34,
        "password": "pbkdf2_sha256$1200000$iGHEDiqbFFSN4wL60sq3vn$yjShNwOQ3HfjGLe4xEJ1MPMn8ZNTZ5B61SYN5ro32CA=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-09-02 18:16:26.450606+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": False,
        "date_joined": "2026-09-02 18:16:26.452044+00:00",
        "last_login": "2026-09-06 20:46:39.357641+00:00",
    },
    {
        "email": "pesalcedo@gmail.com",
        "username": "pesalcedo@gmail.com",
        "first_name": "Pedro",
        "last_name": "Salcedo",
        "age": 46,
        "password": "pbkdf2_sha256$1200000$Cm4fiT2n8NkZaz7o6P7va1$oyMHTtC0wp9paQ+FVQKqkmQFHZQwnm3ghCOaDVmuUYY=",
        "is_active": True,
        "is_staff": False,
        "is_superuser": False,
        "accepted_terms": True,
        "terms_accepted_at": "2026-09-05 17:20:39.437576+00:00",
        "terms_hash": "aa6b792d6a269edc729520e622a8436035c972a1e16adab080a02c623f231ed30342a986401842510326aa9a55f04a4ba151bc9ece1231eb3affe420be61f87c",
        "show_influencer_modal": False,
        "es_influencer": True,
        "date_joined": "2026-09-05 17:20:39.440427+00:00",
        "last_login": "2026-09-05 17:31:11.060736+00:00",
    },
]


def unique_username(User, username, email):
    candidate = username or email
    if not User.objects.filter(username=candidate).exclude(email=email).exists():
        return candidate

    base = email.split("@", 1)[0]
    candidate = base
    counter = 2
    while User.objects.filter(username=candidate).exclude(email=email).exists():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def restore_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for item in USERS:
        user, _ = User.objects.get_or_create(email=item["email"])
        user.username = unique_username(User, item["username"], item["email"])
        user.first_name = item["first_name"]
        user.last_name = item["last_name"]
        user.age = item["age"]
        user.password = item["password"]
        user.is_active = item["is_active"]
        user.is_staff = item["is_staff"]
        user.is_superuser = item["is_superuser"]
        user.accepted_terms = item["accepted_terms"]
        user.terms_accepted_at = parse_datetime(item["terms_accepted_at"]) if item["terms_accepted_at"] else None
        user.terms_hash = item["terms_hash"]
        user.show_influencer_modal = item["show_influencer_modal"]
        user.es_influencer = item["es_influencer"]
        user.date_joined = parse_datetime(item["date_joined"])
        user.last_login = parse_datetime(item["last_login"]) if item["last_login"] else None
        user.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_ensure_admin_user"),
    ]

    operations = [
        migrations.RunPython(restore_users, noop),
    ]
