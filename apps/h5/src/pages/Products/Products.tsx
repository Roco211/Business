import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryApi } from '../../api/inventory';
import { authStore } from '../../store/auth';
import Loading from '../../components/Loading';
import type { InventoryItem } from '../../types';
import './Products.css';

export default function Products() {
  const navigate = useNavigate();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!authStore.isLoggedIn()) {
      navigate('/login', { replace: true });
      return;
    }
    loadItems();
  }, [navigate]);

  const loadItems = async () => {
    setLoading(true);
    try {
      const res = await inventoryApi.getItems();
      setItems(res.data.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  const filtered = search
    ? items.filter(i => i.name.toLowerCase().includes(search.toLowerCase()) || i.category.toLowerCase().includes(search.toLowerCase()))
    : items;

  return (
    <div className="products-page">
      <div className="products-header">
        <div className="products-title">商品管理</div>
        <div className="products-search">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
          <input type="text" placeholder="搜索商品名称或分类" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="products-body">
        {loading ? <Loading /> : filtered.length === 0 ? (
          <div className="products-empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ddd" strokeWidth="1.5"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" /></svg>
            <div>暂无商品</div>
          </div>
        ) : (
          <div className="products-list">
            {filtered.map(item => {
              const isLow = item.is_low_stock;
              return (
                <div key={item.item_id} className="product-card">
                  <div className="product-card-header">
                    <div className="product-card-name">{item.name}</div>
                    {isLow && <span className="product-card-tag danger">库存不足</span>}
                  </div>
                  <div className="product-card-meta">
                    <span>{item.category || '未分类'}</span>
                    <span>{item.default_unit}</span>
                  </div>
                  <div className="product-card-stats">
                    <div className="product-card-stat">
                      <div className="label">库存</div>
                      <div className="value" style={{ color: isLow ? '#fe2c55' : '#1a1a2e' }}>{item.current_stock}</div>
                    </div>
                    <div className="product-card-stat">
                      <div className="label">单价</div>
                      <div className="value">{item.unit_price}</div>
                    </div>
                    <div className="product-card-stat">
                      <div className="label">阈值</div>
                      <div className="value">{item.low_stock_threshold}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
