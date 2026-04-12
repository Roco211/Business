import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../../api/dashboard';
import { inventoryApi } from '../../api/inventory';
import { authStore } from '../../store/auth';
import Loading from '../../components/Loading';
import DetailPage from '../../components/DetailPage';
import Toast from '../../components/Toast';
import { useToast } from '../../hooks/useToast';
import type { DashboardData, RevenueData, TransactionData, InventoryItem, RecommendationsData } from '../../types';
import './Home.css';

interface RawData {
  dash: DashboardData;
  rev: RevenueData;
  items: InventoryItem[];
  trans: TransactionData;
  rec: RecommendationsData;
}

function formatNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  if (n === 0) return '0';
  return Number(n.toFixed(n % 1 === 0 ? 0 : 2)).toString();
}

export default function Home() {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [data, setData] = useState<RawData | null>(null);
  const [loading, setLoading] = useState(true);

  // Detail state
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailTitle, setDetailTitle] = useState('');
  const [detailSubtitle, setDetailSubtitle] = useState('');
  const [detailContent, setDetailContent] = useState<React.ReactNode>(null);

  // Stock operation state
  const [stockInQty, setStockInQty] = useState('');
  const [stockInNote, setStockInNote] = useState('');
  const [stockOutQty, setStockOutQty] = useState('');
  const [stockOutNote, setStockOutNote] = useState('');
  const [, setCurrentItemId] = useState('');
  const [, setCurrentItemName] = useState('');
  const [, setCurrentItemUnit] = useState('件');

  useEffect(() => {
    if (!authStore.isLoggedIn()) {
      navigate('/login', { replace: true });
      return;
    }
    loadData();
  }, [navigate]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [dashR, revR, itemsR, transR, recR] = await Promise.all([
        dashboardApi.getDashboard(),
        dashboardApi.getRevenue(),
        inventoryApi.getItems(),
        dashboardApi.getTransactions(),
        dashboardApi.getRecommendations(),
      ]);
      setData({
        dash: dashR.data.data,
        rev: revR.data.data,
        items: itemsR.data.data,
        trans: transR.data.data,
        rec: recR.data.data,
      });
    } catch (e) {
      console.error('Load error:', e);
    } finally {
      setLoading(false);
    }
  };

  const openDetail = (title: string, subtitle: string, content: React.ReactNode) => {
    setDetailTitle(title);
    setDetailSubtitle(subtitle);
    setDetailContent(content);
    setDetailOpen(true);
  };

  const closeDetail = () => {
    setDetailOpen(false);
    setStockInQty('');
    setStockInNote('');
    setStockOutQty('');
    setStockOutNote('');
  };

  // Stock operations
  const doStockIn = useCallback(async (itemId: string, itemName: string, unit: string) => {
    const qty = parseInt(stockInQty);
    if (!qty || qty <= 0) { showToast('请输入有效数量', 'error'); return; }
    try {
      await inventoryApi.stockIn({ item_id: itemId, quantity: qty, reason: stockInNote || '补货入库' });
      showToast(`${itemName} 入库 +${qty} ${unit}`, 'success');
      setStockInQty('');
      setTimeout(() => { closeDetail(); loadData(); }, 1200);
    } catch { showToast('入库失败', 'error'); }
  }, [stockInQty, stockInNote, showToast]);

  const doStockOut = useCallback(async (itemId: string, itemName: string, unit: string) => {
    const qty = parseInt(stockOutQty);
    if (!qty || qty <= 0) { showToast('请输入有效数量', 'error'); return; }
    try {
      await inventoryApi.stockOut({ item_id: itemId, quantity: qty, reason: stockOutNote || '销售出库' });
      showToast(`${itemName} 出库 -${qty} ${unit}`, 'success');
      setStockOutQty('');
      setTimeout(() => { closeDetail(); loadData(); }, 1200);
    } catch { showToast('出库失败', 'error'); }
  }, [stockOutQty, stockOutNote, showToast]);

  // Detail pages
  const openRevenueDetail = () => {
    if (!data) return;
    const { rev, trans } = data;
    const todayEvents = trans.transactions || [];
    openDetail('营收详情', '今日', (
      <>
        <div className="detail-stat-row">
          <div className="detail-stat"><div className="label">今日营业额</div><div className="value">{formatNum(rev.today_revenue)}</div></div>
          <div className="detail-stat"><div className="label">本周营收</div><div className="value">{formatNum(rev.week_revenue)}</div></div>
        </div>
        <div className="detail-stat-row">
          <div className="detail-stat"><div className="label">出库笔数</div><div className="value">{trans.today_stats?.stock_out_count || 0}</div></div>
          <div className="detail-stat"><div className="label">入库笔数</div><div className="value">{trans.today_stats?.stock_in_count || 0}</div></div>
          <div className="detail-stat"><div className="label">客单价</div><div className="value">{formatNum((trans.today_stats?.stock_out_count || 0) > 0 ? rev.today_revenue / (trans.today_stats?.stock_out_count || 1) : 0)}</div></div>
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, margin: '16px 0 8px' }}>今日流水</div>
        {todayEvents.slice(0, 10).map((ev, i) => {
          const isOut = ev.event_type === 'stock_out';
          return (
            <div key={i} className="detail-list-item">
              <div className="detail-list-icon" style={{ background: isOut ? 'rgba(254,44,85,0.15)' : 'rgba(37,244,238,0.15)' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isOut ? '#fe2c55' : '#25f4ee'} strokeWidth="2"><path d={isOut ? 'M7 17l5 5 5-5M12 12V2' : 'M17 7l-5-5-5 5M12 2v10'} /></svg>
              </div>
              <div className="detail-list-info">
                <div className="detail-list-name">{ev.item_name}</div>
                <div className="detail-list-desc">{ev.quantity} {ev.unit} {ev.created_at?.slice(11, 16)}</div>
              </div>
              <div className="detail-list-right">
                <div className="detail-list-value" style={{ color: isOut ? '#fe2c55' : '#25f4ee' }}>{isOut ? '-' : '+'}{ev.quantity}</div>
              </div>
            </div>
          );
        })}
        <button className="detail-action-btn secondary" onClick={() => openTransactionsDetail()}>查看全部流水</button>
      </>
    ));
  };

  const openTransactionsDetail = () => {
    if (!data) return;
    openDetail('交易流水', '全部记录', (
      <>
        {data.trans.transactions.map((ev, i) => {
          const isOut = ev.event_type === 'stock_out';
          return (
            <div key={i} className="detail-list-item">
              <div className="detail-list-icon" style={{ background: isOut ? 'rgba(254,44,85,0.15)' : 'rgba(37,244,238,0.15)' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isOut ? '#fe2c55' : '#25f4ee'} strokeWidth="2"><path d={isOut ? 'M7 17l5 5 5-5M12 12V2' : 'M17 7l-5-5-5 5M12 2v10'} /></svg>
              </div>
              <div className="detail-list-info">
                <div className="detail-list-name">{ev.item_name}</div>
                <div className="detail-list-desc">{ev.created_at?.slice(5, 16)}</div>
              </div>
              <div className="detail-list-right">
                <div className="detail-list-value" style={{ color: isOut ? '#fe2c55' : '#25f4ee' }}>{isOut ? '-' : '+'}{ev.quantity} {ev.unit}</div>
              </div>
            </div>
          );
        })}
      </>
    ));
  };

  const openInventoryDetail = async () => {
    openDetail('库存管理', '全部商品', <Loading />);
    try {
      const res = await inventoryApi.getItems();
      const items = res.data.data.sort((a, b) => a.current_stock - b.current_stock);
      const lowCount = items.filter(i => i.is_low_stock).length;
      setDetailContent(
        <>
          <div className="detail-stat-row">
            <div className="detail-stat"><div className="label">总SKU</div><div className="value">{items.length}</div></div>
            <div className="detail-stat"><div className="label">预警商品</div><div className="value" style={{ color: '#fe2c55' }}>{lowCount}</div></div>
          </div>
          {items.map((item) => {
            const isLow = item.is_low_stock;
            return (
              <div key={item.item_id} className="detail-list-item" onClick={() => openProductDetail(item.item_id, item.name)}>
                <div className="detail-list-icon" style={{ background: isLow ? 'rgba(254,44,85,0.15)' : '#f5f6fa' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isLow ? '#fe2c55' : '#999'} strokeWidth="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" /></svg>
                </div>
                <div className="detail-list-info">
                  <div className="detail-list-name">{item.name}</div>
                  <div className="detail-list-desc">{item.category || '未分类'}</div>
                </div>
                <div className="detail-list-right">
                  <div className="detail-list-value">{item.current_stock} {item.default_unit}</div>
                  <div className={`detail-list-tag ${isLow ? 'danger' : 'success'}`}>{isLow ? '需补货' : '正常'}</div>
                </div>
              </div>
            );
          })}
        </>
      );
    } catch {
      setDetailContent(<div style={{ textAlign: 'center', color: '#bbb', padding: 30 }}>加载失败</div>);
    }
  };

  const openProductDetail = (itemId: string, itemName: string) => {
    setCurrentItemId(itemId);
    setCurrentItemName(itemName);
    const item = data?.items.find(i => i.item_id === itemId);
    const stock = item?.current_stock || 0;
    const unit = item?.default_unit || '件';
    const threshold = item?.low_stock_threshold || 5;
    const isLow = stock <= threshold;
    setCurrentItemUnit(unit);
    openDetail(itemName, item?.category || '未分类', (
      <>
        <div className="detail-stat-row">
          <div className="detail-stat"><div className="label">当前库存</div><div className="value" style={{ color: isLow ? '#fe2c55' : 'inherit' }}>{stock} {unit}</div></div>
          <div className="detail-stat"><div className="label">安全阈值</div><div className="value">{threshold}</div></div>
          <div className="detail-stat"><div className="label">单价</div><div className="value">{item?.unit_price || 0}</div></div>
        </div>
        <div className="stock-form">
          <div className="form-title">快速入库</div>
          <div className="form-row">
            <span className="form-label">数量</span>
            <input className="form-input" type="number" placeholder="输入入库数量" min="1" value={stockInQty} onChange={e => setStockInQty(e.target.value)} />
          </div>
          <div className="form-row">
            <span className="form-label">备注</span>
            <input className="form-input" type="text" placeholder="采购入库（可选）" value={stockInNote} onChange={e => setStockInNote(e.target.value)} />
          </div>
          <button className="detail-action-btn primary" onClick={() => doStockIn(itemId, itemName, unit)}>确认入库</button>
        </div>
        <div className="stock-form" style={{ marginTop: 8 }}>
          <div className="form-title">快速出库</div>
          <div className="form-row">
            <span className="form-label">数量</span>
            <input className="form-input" type="number" placeholder="输入出库数量" min="1" max={stock} value={stockOutQty} onChange={e => setStockOutQty(e.target.value)} />
          </div>
          <div className="form-row">
            <span className="form-label">备注</span>
            <input className="form-input" type="text" placeholder="销售出库（可选）" value={stockOutNote} onChange={e => setStockOutNote(e.target.value)} />
          </div>
          <button className="detail-action-btn secondary" onClick={() => doStockOut(itemId, itemName, unit)}>确认出库</button>
        </div>
      </>
    ));
  };

  const openLowStockDetail = () => {
    if (!data) return;
    const lowItems = data.items.filter(i => i.is_low_stock);
    openDetail('库存预警', `${lowItems.length}个商品需要补货`, (
      <>
        <div className="detail-stat-row">
          <div className="detail-stat"><div className="label">预警商品</div><div className="value" style={{ color: lowItems.length > 0 ? '#fe2c55' : '#00b96b' }}>{lowItems.length}</div></div>
          <div className="detail-stat"><div className="label">库存总值</div><div className="value">{formatNum(data.dash.total_value)}</div></div>
        </div>
        {lowItems.map(item => {
          const pct = Math.round((item.current_stock / Math.max(item.low_stock_threshold, 1)) * 100);
          const color = pct < 20 ? '#fe2c55' : pct < 50 ? '#faad14' : '#25f4ee';
          return (
            <div key={item.item_id} className="detail-list-item" onClick={() => openProductDetail(item.item_id, item.name)}>
              <div className="detail-list-icon" style={{ background: 'rgba(254,44,85,0.15)' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fe2c55" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
              </div>
              <div className="detail-list-info">
                <div className="detail-list-name">{item.name}</div>
                <div className="detail-list-desc">
                  <div className="progress-track" style={{ marginTop: 4 }}><div className="progress-fill" style={{ width: `${pct}%`, background: color }} /></div>
                </div>
              </div>
              <div className="detail-list-right">
                <div className="detail-list-value" style={{ color }}>剩余 {item.current_stock} {item.default_unit}</div>
              </div>
            </div>
          );
        })}
      </>
    ));
  };

  const openAIDetail = () => {
    if (!data) return;
    const recs = data.rec.recommendations || [];
    openDetail('AI 经营建议', '智能分析', (
      <>
        <div style={{ padding: 16, background: '#eef1ff', border: '1px solid rgba(77,107,254,0.15)', borderRadius: 12, marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: '#999', marginBottom: 6 }}>AI 分析结论</div>
          <div style={{ fontSize: 15, lineHeight: 1.6 }}>{recs.length > 0 ? (recs[0].suggestion || recs[0].title || '暂无特别建议') : '添加更多经营数据后，AI 将提供个性化建议'}</div>
        </div>
        {recs.map((r, i) => (
          <div key={i} className="detail-list-item">
            <div className="detail-list-icon" style={{ background: 'rgba(77,107,254,0.15)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4d6bfe" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" /></svg>
            </div>
            <div className="detail-list-info">
              <div className="detail-list-name">{r.title || r.name || '建议'}</div>
              <div className="detail-list-desc">{r.message || r.suggestion || r.action || ''}</div>
            </div>
            <div className={`detail-list-tag ${r.type === 'urgent' ? 'danger' : r.type === 'warning' ? 'info' : 'success'}`}>{r.type === 'urgent' ? '紧急' : r.type === 'warning' ? '关注' : '参考'}</div>
          </div>
        ))}
        <button className="detail-action-btn primary" onClick={() => { closeDetail(); navigate('/chat'); }}>问AI更多</button>
      </>
    ));
  };

  if (loading) return <div className="home-page"><Loading /></div>;
  if (!data) return <div className="home-page"><Loading text="加载失败" /></div>;

  const { dash, rev, items, trans, rec } = data;
  const todayRevenue = rev.today_revenue;
  const weekRevenue = rev.week_revenue;
  const orderCount = trans.today_stats?.stock_out_count || 0;
  const lowStock = items.filter(i => i.is_low_stock);
  const topItems = rev.top_items || [];
  const recs = rec.recommendations || [];
  const maxSold = topItems.length > 0 ? Math.max(...topItems.map(i => i.total_sold || 0), 1) : 1;

  return (
    <div className="home-page">
      {/* Status bar mock */}
      <div className="status-bar">
        <span>9:41</span>
        <span />
      </div>

      {/* Top nav */}
      <div className="top-nav">
        <div className="top-nav-center">
          <button className="top-tab active">关注</button>
          <button className="top-tab">推荐</button>
        </div>
      </div>

      {/* Card feed */}
      <div className="card-feed">
        {/* Card 1: 今日营业 */}
        <div className="video-card">
          <div className="video-bg" />
          <div className="card-content">
            <div className="employee-badge"><span className="dot" style={{ background: '#3370ff' }} />营业数据员</div>
            <div className="card-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#4d6bfe" strokeWidth="1.5"><rect x="1" y="4" width="22" height="16" rx="2" /><line x1="1" y1="10" x2="23" y2="10" /></svg>
            </div>
            <div className="title">今日营业数据</div>
            <div className="sub">上滑查看热销排行</div>

            <div className="data-hero clickable" onClick={openRevenueDetail}>
              <div className="label">今日营业额</div>
              <div className="value">{formatNum(todayRevenue)}</div>
              <div className={`change ${todayRevenue > 0 ? 'up' : 'down'}`}>{todayRevenue > 0 ? '较昨日增长' : '持平'}</div>
            </div>
            <div className="data-row">
              <div className="data-mini clickable" onClick={openRevenueDetail}>
                <div className="label">出库笔数</div>
                <div className="value">{orderCount}</div>
              </div>
              <div className="data-mini clickable" onClick={openRevenueDetail}>
                <div className="label">入库笔数</div>
                <div className="value">{trans.today_stats?.stock_in_count || 0}</div>
              </div>
              <div className="data-mini clickable" onClick={openInventoryDetail}>
                <div className="label">库存总值</div>
                <div className="value">{formatNum(dash.total_value)}</div>
              </div>
            </div>
            <div className="data-row">
              <div className="data-mini clickable" onClick={openRevenueDetail}>
                <div className="label">本周营收</div>
                <div className="value">{formatNum(weekRevenue)}</div>
              </div>
              <div className="data-mini clickable" onClick={openInventoryDetail}>
                <div className="label">SKU数</div>
                <div className="value">{dash.total_items}</div>
              </div>
              <div className="data-mini clickable" onClick={openInventoryDetail}>
                <div className="label">商品种类</div>
                <div className="value">{dash.categories.length}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: 热销排行 */}
        <div className="video-card">
          <div className="video-bg" />
          <div className="card-content">
            <div className="employee-badge"><span className="dot" style={{ background: '#e91e63' }} />销售分析员</div>
            <div className="card-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#e91e63" strokeWidth="1.5"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>
            </div>
            <div className="title">热销排行榜</div>
            <div className="sub">本周 · 按销量排序</div>

            <div className="data-hero clickable" onClick={openTransactionsDetail}>
              <div className="label">本周热销 TOP</div>
              <div className="value" style={{ fontSize: 24 }}>累计 {formatNum(weekRevenue)}</div>
            </div>
            <div className="product-list">
              {topItems.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#bbb', padding: 20 }}>暂无销售数据</div>
              ) : topItems.slice(0, 6).map((item, i) => {
                const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
                const pct = Math.round((item.total_sold / maxSold) * 100);
                return (
                  <div key={i} className="product-item clickable" onClick={() => openProductDetail(item.item_id || '', item.name)}>
                    <div className={`product-rank ${rankClass}`}>{i + 1}</div>
                    <div className="product-info">
                      <div className="product-name">{item.name}</div>
                      <div className="product-stat">销量 {formatNum(item.total_sold)} {formatNum(item.total_revenue)}</div>
                    </div>
                    <div className="product-bar"><div className="product-bar-fill" style={{ width: `${pct}%` }} /></div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Card 3: 库存预警 */}
        <div className="video-card">
          <div className="video-bg" />
          <div className="card-content">
            <div className="employee-badge"><span className="dot" style={{ background: '#00b96b' }} />库存守护员</div>
            <div className="card-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#00b96b" strokeWidth="1.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
            </div>
            <div className="title">库存预警中心</div>
            <div className="sub">{lowStock.length > 0 ? `${lowStock.length}个商品需要补货` : '所有库存正常'}</div>

            <div className="data-hero clickable" onClick={openInventoryDetail}>
              <div className="label">库存预警商品</div>
              <div className="value" style={{ fontSize: 48, color: lowStock.length > 0 ? '#fe2c55' : '#25f4ee' }}>{lowStock.length}</div>
              <div className="sub" style={{ color: '#999' }}>{lowStock.length > 0 ? '低于安全库存' : '库存状态良好'}</div>
            </div>
            {lowStock.slice(0, 5).map(item => {
              const maxStock = Math.max(item.low_stock_threshold, item.current_stock);
              const pct = Math.round((item.current_stock / Math.max(maxStock, 1)) * 100);
              const color = pct < 20 ? '#fe2c55' : pct < 50 ? '#faad14' : '#25f4ee';
              return (
                <div key={item.item_id} className="progress-item clickable" onClick={() => openProductDetail(item.item_id, item.name)}>
                  <div className="row"><span className="name">{item.name}</span><span className="stat" style={{ color }}>剩余 {item.current_stock} {item.default_unit}</span></div>
                  <div className="progress-track"><div className="progress-fill" style={{ width: `${pct}%`, background: color }} /></div>
                </div>
              );
            })}
            <div className="data-row" style={{ marginTop: 12 }}>
              <div className="data-mini clickable" onClick={openInventoryDetail}><div className="label">库存总值</div><div className="value">{formatNum(dash.total_value)}</div></div>
              <div className="data-mini clickable" onClick={openInventoryDetail}><div className="label">SKU数</div><div className="value">{dash.total_items}</div></div>
              <div className="data-mini clickable" onClick={openTransactionsDetail}><div className="label">今日事件</div><div className="value">{dash.today_events}</div></div>
            </div>
          </div>
        </div>

        {/* Card 4: AI建议 */}
        <div className="video-card">
          <div className="video-bg" />
          <div className="card-content">
            <div className="employee-badge"><span className="dot" style={{ background: '#9c27b0' }} />AI参谋</div>
            <div className="card-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9c27b0" strokeWidth="1.5"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9" /></svg>
            </div>
            <div className="title">AI 经营建议</div>
            <div className="sub">根据销售数据为你推荐进货方案</div>

            <div className="data-hero clickable" onClick={openAIDetail}>
              <div className="label">AI 经营建议</div>
              <div className="value" style={{ fontSize: 18, lineHeight: 1.6 }}>{recs.length > 0 ? (recs[0].suggestion || recs[0].title || '暂无特别建议') : '正在分析经营数据...'}</div>
            </div>
            <div className="data-row">
              <div className="data-mini clickable" onClick={openInventoryDetail}><div className="label">商品总数</div><div className="value">{dash.total_items}</div></div>
              <div className="data-mini clickable" onClick={openLowStockDetail}><div className="label">预警商品</div><div className="value" style={{ color: lowStock.length > 0 ? '#fe2c55' : 'inherit' }}>{lowStock.length}</div></div>
              <div className="data-mini clickable" onClick={openInventoryDetail}><div className="label">品类数</div><div className="value">{dash.categories.length}</div></div>
            </div>
          </div>
        </div>
      </div>

      {/* Detail page */}
      <DetailPage open={detailOpen} title={detailTitle} subtitle={detailSubtitle} onClose={closeDetail}>
        {detailContent}
      </DetailPage>

      <Toast {...toast} />
    </div>
  );
}
