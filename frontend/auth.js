document.getElementById('btn-login').addEventListener('click', () => authenticate('/api/login'));
document.getElementById('btn-register').addEventListener('click', () => authenticate('/api/register'));

async function authenticate(endpoint) {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const errorMsg = document.getElementById('error-msg');
    errorMsg.style.display = 'none';

    if (!email || !password) {
        showError('Пожалуйста, заполните все поля.');
        return;
    }

    try {
        let response;
        if (endpoint === '/api/login') {
            // OAuth2 форма ожидает application/x-www-form-urlencoded
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);
            response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });
        } else {
            // Регистрация ожидает JSON
            response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Ошибка авторизации');
        }

        // Сохраняем токен и переходим на карту
        localStorage.setItem('token', data.access_token);
        window.location.href = '/';

    } catch (err) {
        showError(err.message);
    }
}

function showError(msg) {
    const errorMsg = document.getElementById('error-msg');
    errorMsg.innerText = msg;
    errorMsg.style.display = 'block';
}