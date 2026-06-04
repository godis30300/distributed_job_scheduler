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
        ('shell', 'Shell Script'),
        ('python_script', 'Python Script'),
        ('api_call', 'API 呼叫 (HTTP)'),
    ]
    STATUS_CHOICES = [
        ('enabled', '啟用'),
        ('disabled', '停用'),
    ]

    task_name = forms.CharField(label='任務名稱', max_length=200)
    description = forms.CharField(label='任務描述', widget=forms.Textarea(attrs={'rows': 2}), required=False)
    status = forms.ChoiceField(label='狀態', choices=STATUS_CHOICES)
    
    schedule_type = forms.ChoiceField(label='排程類型', choices=SCHEDULE_CHOICES)
    cron_expression = forms.CharField(label='Cron Expression', required=False, help_text='例如：0 2 * * *')
    interval_seconds = forms.IntegerField(label='Interval 秒數', required=False, min_value=1)
    
    action = forms.ChoiceField(label='任務動作類型', choices=ACTION_CHOICES)
    
    # API Call parameters
    api_method = forms.ChoiceField(label='HTTP 方法', choices=[('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'), ('DELETE', 'DELETE')], required=False, initial='GET')
    api_url = forms.URLField(label='API 網址', required=False, help_text='例如：http://backend:8000/api/system/health')
    
    # Script parameters
    working_dir = forms.CharField(label='工作目錄 (Working Dir)', required=False, help_text='例如：/app/scripts')
    shell_script = forms.CharField(label='腳本名稱 (選填)', required=False, help_text='例如：hello.sh')
    script_content = forms.CharField(label='腳本內容 (Linux Script)', widget=forms.Textarea(attrs={'rows': 10, 'placeholder': '#!/bin/bash\necho "Hello World"'}), required=False)
    
    timeout_seconds = forms.IntegerField(label='Timeout 秒數', min_value=1, initial=300)
    retry_limit = forms.IntegerField(label='Retry 次數', min_value=0, initial=3)
    
    depends_on = forms.MultipleChoiceField(
        label='相依任務 (Depends On)',
        required=False,
        widget=forms.SelectMultiple(attrs={'size': '5'}),
        help_text='選取此任務執行前必須成功完成的任務。'
    )
