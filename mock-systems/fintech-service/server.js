/**
 * HỆ THỐNG 2: FINTECH & E-WALLET SERVICE (Port 8020 - Node.js)
 * Service ví điện tử quản lý giao dịch & có Agent tài chính tự động.
 * Demo tính năng: Chốt chặn can thiệp của con người (Human-in-the-Loop Approval).
 */

const http = require('http');
const { AgentSentinelNode } = require('./agentHubClient');

const PORT = 8020;
const sentinel = new AgentSentinelNode('http://localhost:8000');

// Mock Số dư tài khoản ví điện tử
const WALLET_DB = {
  'ACC-9988': { owner: 'Nguyễn Văn A', balance_vnd: 12500000, status: 'ACTIVE' },
};

const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200);
    return res.end(JSON.stringify({
      status: 'healthy',
      service: 'Fintech & E-Wallet Service',
      port: PORT,
      framework: 'Node.js Native',
    }));
  }

  // API 1: YÊU CẦU CHUYỂN TIỀN (TRIGGER HUMAN-IN-THE-LOOP)
  if (req.method === 'POST' && req.url === '/api/transfer') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      let payload = {};
      try { payload = JSON.parse(body || '{}'); } catch (e) {}

      const accountId = payload.account_id || 'ACC-9988';
      const recipient = payload.recipient || 'EVN-ELECTRIC-BILL';
      const amountVnd = payload.amount || 2500000;

      console.log(`[Fintech Service :${PORT}] Nhận yêu cầu thanh toán ${amountVnd.toLocaleString()}₫ từ ví ${accountId}`);

      // 1. Khởi tạo phiên Agent với AgentGuard Hub
      const session = await sentinel.startRun({
        agentName: 'Fintech_Payment_Agent',
        prompt: `Yêu cầu trích ví ${accountId} thanh toán ${amountVnd}₫ cho hóa đơn ${recipient}`,
        maxSteps: 4,
        budgetUsd: 0.30,
        userId: accountId,
      });

      if (session) {
        // 2. Bước 1: Tra cứu số dư (Hợp lệ)
        await session.logStep({
          thought: `Tra cứu số dư ví ${accountId} xem có đủ ${amountVnd}₫ không.`,
          toolName: 'check_wallet_balance',
          toolInput: { account_id: accountId },
          toolOutput: WALLET_DB[accountId] || { balance_vnd: 0 },
          tokensUsed: 150,
          costUsd: 0.00004,
          isBillable: true,
        });

        // 3. Bước 2: Chuẩn bị chuyển tiền (HÀNH ĐỘNG NHẠY CẢM TIỀN TỆ - BẮT BUỘC DỪNG XIN DUYỆT)
        console.log(`[Fintech Service :${PORT}] 🛡️ Kích hoạt chốt chặn: Lệnh 'execute_bank_transfer' cần người phê duyệt!`);
        await session.logStep({
          thought: `Số dư khả dụng đủ. Cố tình thực thi lệnh chuyển tiền 'execute_bank_transfer' (Hành động nhạy cảm - CẦN PHÊ DUYỆT).`,
          toolName: 'execute_bank_transfer',
          toolInput: { from: accountId, to: recipient, amount_vnd: amountVnd },
          toolOutput: null,
          tokensUsed: 120,
          costUsd: 0.00003,
          isBillable: true,
        });

        // Agent tự động dừng lại ở trạng thái WAITING_APPROVAL
        await session.fail(`PAUSED: Hành động chuyển tiền 2.500.000₫ đang tạm dừng chờ người quản trị bấm Authorize trên Dashboard :8000.`);
      }

      res.writeHead(202);
      return res.end(JSON.stringify({
        success: false,
        status: 'WAITING_HUMAN_APPROVAL',
        message: 'Lệnh chuyển tiền đã bị AgentGuard tạm dừng khẩn cấp để chờ con người xác thực trên Dashboard :8000.',
        hub_run_id: session?.runId || null,
        transaction_details: { accountId, recipient, amountVnd },
      }));
    });
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Endpoint not found' }));
});

server.listen(PORT, () => {
  console.log(`🚀 Khởi chạy Hệ Thống 2 (Fintech & E-Wallet Service) trên cổng ${PORT}...`);
});
