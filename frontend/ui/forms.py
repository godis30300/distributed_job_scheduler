from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(label='帳號', max_length=150)
    password = forms.CharField(label='密碼', widget=forms.PasswordInput)


class RegisterForm(forms.Form):
    username = forms.CharField(label='帳號', max_length=150)
    email = forms.EmailField(label='Email')
    password = forms.CharField(label='密碼', widget=forms.PasswordInput)


class JobForm(forms.Form):
    SCHEDULE_CHOICES = [
        ('manual', '手動'),
        ('cron', 'Cron'),
        ('interval', 'Interval'),
    ]
    ACTION_CHOICES = [
        ('report', '生成日報表'),
        ('email', '發送 Email'),
        ('backup', '備份資料庫'),
        ('fail-test', '失敗測試'),
        ('long-task', '長時間任務'),
    ]
    STATUS_CHOICES = [
        ('enabled', '啟用'),
        ('disabled', '停用'),
    ]

    task_name = forms.CharField(label='任務名稱', max_length=200)
    status = forms.ChoiceField(label='狀態', choices=STATUS_CHOICES)
    schedule_type = forms.ChoiceField(label='排程類型', choices=SCHEDULE_CHOICES)
    cron_expression = forms.CharField(label='Cron Expression', required=False, help_text='例如：0 2 * * *')
    interval_seconds = forms.IntegerField(label='Interval 秒數', required=False, min_value=1)
    action = forms.ChoiceField(label='任務動作', choices=ACTION_CHOICES)
    timeout_seconds = forms.IntegerField(label='Timeout 秒數', min_value=1, initial=300)
    retry_limit = forms.IntegerField(label='Retry 次數', min_value=0, initial=3)
