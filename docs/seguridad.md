# Seguridad operativa

El bot sólo debe ejecutarse con `ALLOWED_USER_IDS` configurado. Los handlers
aceptan únicamente chats privados de esos usuarios. Si la variable está vacía,
el proceso no inicia.

Las credenciales viven fuera de Git (`.env` y `service_account.json`) y deben
tener permisos `600`. Los estados de cuenta PDF y los logs quedan fuera del
repositorio. Si una credencial fue expuesta, hay que revocarla y crear otra:

1. Revoca y regenera el token en BotFather.
2. Revoca la clave de Gemini y crea una nueva en Google AI Studio/Cloud.
3. Rota la clave JSON de la cuenta de servicio y limita su acceso únicamente a
   la hoja necesaria.
4. Revisa el historial de GitHub y elimina cualquier copia de documentos
   financieros o credenciales que se haya publicado.

El bot limita a 30 solicitudes por usuario por minuto, mensajes de 4.000
caracteres y fotos de 8 MiB. Estos límites se pueden reducir mediante el
`.env` local.
