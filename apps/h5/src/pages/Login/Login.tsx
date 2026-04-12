import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { authStore } from '../../store/auth';
import Toast from '../../components/Toast';
import { useToast } from '../../hooks/useToast';
import type { User } from '../../types';
import './Login.css';

type PanelTab = 'login' | 'register' | 'forgot';

export default function Login() {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [agreed, setAgreed] = useState(true);
  const [panelOpen, setPanelOpen] = useState(false);
  const [tab, setTab] = useState<PanelTab>('login');
  const [loading, setLoading] = useState(false);
  const [showPwd, setShowPwd] = useState(false);

  // 登录表单
  const [loginUser, setLoginUser] = useState('');
  const [loginPwd, setLoginPwd] = useState('');

  // 注册表单
  const [regUser, setRegUser] = useState('');
  const [regPwd, setRegPwd] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regCode, setRegCode] = useState('');
  const [codeBtnText, setCodeBtnText] = useState('获取验证码');
  const [codeDisabled, setCodeDisabled] = useState(false);

  // 忘记密码
  const [forgotContact, setForgotContact] = useState('');
  const [forgotCode, setForgotCode] = useState('');
  const [forgotNewPwd, setForgotNewPwd] = useState('');

  const checkAgree = () => {
    if (!agreed) {
      showToast('请先阅读并同意用户协议与隐私政策', 'error');
      return false;
    }
    return true;
  };

  const saveAuth = (token: string, username: string, nickname?: string) => {
    const user: User = { user_id: '', username, nickname, shop_id: '' };
    authStore.save(token, user);
  };

  // 一键登录
  const handleOneClick = async () => {
    if (!checkAgree()) return;
    setLoading(true);
    try {
      await authApi.sendCode('13888888888', undefined, 'register');
      const regRes = await authApi.register({ username: 'user_8888', password: '888888', phone: '13888888888', code: '888888' });
      if (regRes.data.success && regRes.data.token) {
        saveAuth(regRes.data.token, regRes.data.username || 'user_8888', regRes.data.nickname);
        navigate('/', { replace: true });
        return;
      }
      const loginRes = await authApi.login({ username: 'user_8888', password: '888888' });
      if (loginRes.data.success && loginRes.data.token) {
        saveAuth(loginRes.data.token, loginRes.data.username || 'user_8888', loginRes.data.nickname);
        navigate('/', { replace: true });
        return;
      }
      showToast(loginRes.data.message || '登录失败', 'error');
    } catch {
      showToast('网络错误，请重试', 'error');
    } finally {
      setLoading(false);
    }
  };

  // 密码登录
  const handleLogin = async () => {
    if (!checkAgree()) return;
    if (!loginUser) { showToast('请输入账号', 'error'); return; }
    if (!loginPwd) { showToast('请输入密码', 'error'); return; }
    setLoading(true);
    try {
      const res = await authApi.login({ username: loginUser, password: loginPwd });
      if (res.data.success && res.data.token) {
        saveAuth(res.data.token, res.data.username || loginUser, res.data.nickname);
        navigate('/', { replace: true });
      } else {
        showToast(res.data.message || '登录失败', 'error');
      }
    } catch {
      showToast('网络错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  // 发送验证码
  const sendCode = async () => {
    if (!checkAgree()) return;
    const phone = tab === 'register' ? regPhone : forgotContact;
    const email = tab === 'register' ? regEmail : '';
    if (!phone && !email) { showToast('请输入手机号或邮箱', 'error'); return; }
    try {
      await authApi.sendCode(phone || undefined, email || undefined, tab === 'register' ? 'register' : 'reset_password');
      showToast('验证码已发送（演示验证码：888888）');
      setCodeDisabled(true);
      let s = 60;
      const timer = setInterval(() => {
        setCodeBtnText(`${s}秒后重试`);
        s--;
        if (s < 0) { clearInterval(timer); setCodeDisabled(false); setCodeBtnText('获取验证码'); }
      }, 1000);
    } catch {
      showToast('发送失败', 'error');
    }
  };

  // 注册
  const handleRegister = async () => {
    if (!checkAgree()) return;
    if (!regUser || regUser.length < 3) { showToast('用户名至少3个字符', 'error'); return; }
    if (!regPwd || regPwd.length < 6) { showToast('密码至少6位', 'error'); return; }
    if (!regCode) { showToast('请输入验证码', 'error'); return; }
    setLoading(true);
    try {
      const res = await authApi.register({ username: regUser, password: regPwd, phone: regPhone || undefined, email: regEmail || undefined, code: regCode });
      if (res.data.success && res.data.token) {
        saveAuth(res.data.token, res.data.username || regUser, res.data.nickname);
        navigate('/', { replace: true });
      } else {
        showToast(res.data.message || '注册失败', 'error');
      }
    } catch {
      showToast('网络错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  // 重置密码
  const handleReset = async () => {
    if (!checkAgree()) return;
    showToast('密码重置功能开发中', 'error');
  };

  return (
    <div className="login-page">
      <div className="login-top-area">
        <div className="brand-logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
        </div>
        <div className="brand-name">AI五金店大管家</div>
      </div>

      <div className="login-action-area">
        <div className="phone-section">
          <div className="phone-row">
            <span className="phone-number">138****8888</span>
          </div>
          <div className="carrier-text">运营商认证服务</div>
        </div>

        <div className="btn-group">
          <button className="btn-login btn-primary" onClick={handleOneClick} disabled={loading}>
            <svg className="btn-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
              <line x1="12" y1="18" x2="12.01" y2="18" strokeWidth="3" />
            </svg>
            手机号一键登录
          </button>
          <button className="btn-login btn-outline" onClick={() => { if (checkAgree()) showToast('微信登录功能开发中'); }}>
            <svg className="btn-icon" width="22" height="22" viewBox="0 0 24 24" fill="#07c160">
              <path d="M9.5 4C5.91 4 3 6.46 3 9.5c0 1.7.91 3.2 2.31 4.18L4.5 16l2.76-1.38c.65.18 1.33.28 2.04.28h.2c.07 0 .14 0 .2-.02-.14-.42-.2-.86-.2-1.31C9.5 10.24 11.74 8 14.5 8c.34 0 .67.03 1 .08C14.54 5.66 12.25 4 9.5 4z" />
              <path d="M21 13.5c0-2.49-2.24-4.5-5-4.5s-5 2.01-5 4.5 2.24 4.5 5 4.5c.58 0 1.14-.08 1.67-.23L19.5 19l-.72-2.16C20.32 15.78 21 14.7 21 13.5z" />
              <circle cx="12" cy="13.5" r=".8" />
              <circle cx="16" cy="13.5" r=".8" />
            </svg>
            微信登录
          </button>
          <button className="btn-login btn-outline" onClick={() => { if (checkAgree()) setPanelOpen(true); }}>
            <svg className="btn-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" />
              <path d="M7 11V7a5 5 0 0110 0v4" />
            </svg>
            密码登录
          </button>
        </div>

        <div className="agreement">
          <div className={`checkbox ${agreed ? 'checked' : ''}`} onClick={() => setAgreed(!agreed)}>
            {agreed && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>}
          </div>
          <div className="agreement-text">
            我已阅读并同意 <a href="#" onClick={(e) => e.preventDefault()}>用户协议</a> 与 <a href="#" onClick={(e) => e.preventDefault()}>隐私政策</a>
          </div>
        </div>
      </div>

      {/* 密码登录面板 */}
      {panelOpen && (
        <div className="panel-overlay" onClick={(e) => { if (e.target === e.currentTarget) setPanelOpen(false); }}>
          <div className="panel">
            <button className="panel-close" onClick={() => setPanelOpen(false)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
            <div className="panel-handle" />
            <div className="panel-title">账户登录</div>

            <div className="panel-tabs">
              <button className={`panel-tab ${tab === 'login' ? 'active' : ''}`} onClick={() => setTab('login')}>登录</button>
              <button className={`panel-tab ${tab === 'register' ? 'active' : ''}`} onClick={() => setTab('register')}>注册</button>
            </div>

            {tab === 'login' && (
              <div>
                <div className="form-group">
                  <input className="form-input" type="text" placeholder="手机号 / 邮箱 / 用户名" value={loginUser} onChange={(e) => setLoginUser(e.target.value)} />
                </div>
                <div className="form-group">
                  <div className="password-wrap">
                    <input className="form-input" type={showPwd ? 'text' : 'password'} placeholder="密码" value={loginPwd} onChange={(e) => setLoginPwd(e.target.value)} />
                    <button type="button" className="password-toggle" onClick={() => setShowPwd(!showPwd)}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        {showPwd ? (
                          <>
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                          </>
                        ) : (
                          <>
                            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
                            <line x1="1" y1="1" x2="23" y2="23" />
                          </>
                        )}
                      </svg>
                    </button>
                  </div>
                </div>
                <button className="panel-submit" onClick={handleLogin} disabled={loading}>{loading ? '登录中...' : '登录'}</button>
                <div className="panel-links">
                  <a href="#" onClick={(e) => { e.preventDefault(); setTab('forgot'); }}>忘记密码？</a>
                  <a href="#" onClick={(e) => { e.preventDefault(); setTab('register'); }}>没有账户？去注册</a>
                </div>
                <div className="demo-hint">演示验证码：<strong>888888</strong></div>
              </div>
            )}

            {tab === 'register' && (
              <div>
                <div className="form-group">
                  <input className="form-input" type="text" placeholder="用户名（3-50字符）" value={regUser} onChange={(e) => setRegUser(e.target.value)} />
                </div>
                <div className="form-group">
                  <div className="password-wrap">
                    <input className="form-input" type={showPwd ? 'text' : 'password'} placeholder="设置密码（6位以上）" value={regPwd} onChange={(e) => setRegPwd(e.target.value)} />
                    <button type="button" className="password-toggle" onClick={() => setShowPwd(!showPwd)}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div className="form-group">
                  <input className="form-input" type="text" placeholder="手机号（可选）" value={regPhone} onChange={(e) => setRegPhone(e.target.value)} />
                </div>
                <div className="form-group">
                  <input className="form-input" type="email" placeholder="邮箱（可选）" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} />
                </div>
                <div className="form-group">
                  <div className="code-row">
                    <input className="form-input" type="text" placeholder="验证码" maxLength={6} value={regCode} onChange={(e) => setRegCode(e.target.value)} />
                    <button className="code-send-btn" onClick={sendCode} disabled={codeDisabled}>{codeBtnText}</button>
                  </div>
                </div>
                <button className="panel-submit" onClick={handleRegister} disabled={loading}>{loading ? '注册中...' : '注册'}</button>
                <div className="panel-links">
                  <a href="#" onClick={(e) => { e.preventDefault(); setTab('login'); }}>已有账户？去登录</a>
                </div>
                <div className="demo-hint">演示验证码：<strong>888888</strong></div>
              </div>
            )}

            {tab === 'forgot' && (
              <div>
                <div className="form-group">
                  <input className="form-input" type="text" placeholder="手机号 / 邮箱" value={forgotContact} onChange={(e) => setForgotContact(e.target.value)} />
                </div>
                <div className="form-group">
                  <div className="code-row">
                    <input className="form-input" type="text" placeholder="验证码" maxLength={6} value={forgotCode} onChange={(e) => setForgotCode(e.target.value)} />
                    <button className="code-send-btn" onClick={sendCode} disabled={codeDisabled}>{codeBtnText}</button>
                  </div>
                </div>
                <div className="form-group">
                  <div className="password-wrap">
                    <input className="form-input" type="password" placeholder="设置新密码" value={forgotNewPwd} onChange={(e) => setForgotNewPwd(e.target.value)} />
                  </div>
                </div>
                <button className="panel-submit" onClick={handleReset}>重置密码</button>
                <div className="panel-links">
                  <a href="#" onClick={(e) => { e.preventDefault(); setTab('login'); }}>返回登录</a>
                </div>
                <div className="demo-hint">演示验证码：<strong>888888</strong></div>
              </div>
            )}
          </div>
        </div>
      )}

      <Toast {...toast} />
    </div>
  );
}
