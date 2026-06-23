// api/server.js
const express = require('express');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(cors()); // Permite que seu frontend React consuma a API local
app.use(express.json());

// Configuração de conexão segura usando Autenticação Integrada (Windows/Trusted)
const dbConfig = {
    server: 'SPSVSQL39', // Servidor obtido de CONEXOES
    database: 'FINANCA',
    driver: 'msnodesqlv8', // Utiliza autenticação nativa do Windows no Node.js
    options: {
        trustedConnection: true,
        encrypt: false,
        trustServerCertificate: true
    }
};

app.get('/api/telemetria', async (req, res) => {
    try {
        await sql.connect(dbConfig);
        
        // Puxa as métricas e faz o parse do JSON dinâmico diretamente na consulta SQL
        const query = `
            SELECT 
                nome_processo,
                data_execucao,
                total_linhas,
                total_colunas,
                total_nulos,
                detalhes_json
            FROM dbo.[dex-controle-metricas]
            ORDER BY data_execucao DESC
        `;
        
        const result = await sql.query(query);
        
        // Formata o retorno parseando o JSON armazenado na coluna "detalhes_json"
        const dadosFormatados = result.recordset.map(row => ({
            nome_processo: row.nome_processo,
            data_execucao: row.data_execucao,
            total_linhas: row.total_linhas,
            total_colunas: row.total_colunas,
            total_nulos: row.total_nulos,
            detalhes: JSON.parse(row.detalhes_json)
        }));

        res.json(dadosFormatados);
    } catch (err) {
        console.error('Erro ao acessar banco de dados:', err);
        res.status(500).json({ error: 'Erro interno do servidor local' });
    }
});

// Vincula o servidor de forma estrita ao 127.0.0.1 (Localhost)
app.listen(8080, '127.0.0.1', () => {
    console.log('Backend seguro do DEX rodando localmente em http://127.0.0.1:8080');
});
