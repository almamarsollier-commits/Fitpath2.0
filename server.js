const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

require('dotenv').config();

const { MercadoPagoConfig, Preference } = require('mercadopago');

const mpClient = new MercadoPagoConfig({
    accessToken: process.env.MP_ACCESS_TOKEN
});

const preference = new Preference(mpClient);
if (!process.env.MP_ACCESS_TOKEN || !process.env.MP_PUBLIC_KEY) {
    console.error('Faltan las credenciales de Mercado Pago en el archivo .env');
    process.exit(1);
}

console.log('Credenciales de Mercado Pago cargadas correctamente.');
const app = express();
const PORT = 3000;

app.use(express.json());

app.use(express.static(path.join(__dirname, 'Fithpad2.0', 'templates')));

app.use('/statics', express.static(path.join(__dirname, 'Fithpad2.0', 'statics')));

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'Fithpad2.0', 'templates', 'index.html'));
});

const dbFile = path.join(__dirname, 'gimnasio.db');
const db = new sqlite3.Database(dbFile, (err) => {
    if (err) {
        console.error('Error al abrir la base de datos:', err.message);
    } else {
        console.log('Conectado a la base de datos SQLite correctamente.');
    }
});

db.run(`CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    goal TEXT
)`, (err) => {
    if (err) {
        console.error("Error al crear la tabla usuarios:", err.message);
    } else {
        console.log("Tabla 'usuarios' lista o creada con éxito.");
    }
});

app.post('/api/register', (req, res) => {
    const { name, email, password, goal } = req.body;
    const query = `INSERT INTO usuarios (name, email, password, goal) VALUES (?, ?, ?, ?)`;
    db.run(query, [name, email, password, goal], function(err) {
        if (err) return res.status(400).json({ error: "Ya existe una cuenta con ese correo." });
        res.json({ mensaje: "Usuario registrado con éxito", user: { name, email, goal } });
    });
});

app.post('/api/login', (req, res) => {
    const { email, password } = req.body;
    const query = `SELECT * FROM usuarios WHERE email = ? AND password = ?`;
    db.get(query, [email, password], (err, row) => {
        if (err) return res.status(500).json({ error: "Error en el servidor" });
        if (!row) return res.status(401).json({ error: "Correo o contraseña incorrectos." });
        res.json({ mensaje: "Login exitoso", user: { name: row.name, email: row.email, goal: row.goal } });
    });
});

app.listen(PORT, () => {
    console.log(`Servidor corriendo en http://localhost:${PORT}`);
});