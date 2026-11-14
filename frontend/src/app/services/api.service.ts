import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Analysis, Health, OrderRequest, ScanResult } from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  health(): Observable<Health> {
    return this.http.get<Health>(`${this.base}/health`);
  }

  createSession(): Observable<{ session_id: string; created_at: number }> {
    return this.http.post<{ session_id: string; created_at: number }>(
      `${this.base}/sessions`,
      {},
    );
  }

  analysis(symbol: string, resolution = '60'): Observable<Analysis> {
    return this.http.get<Analysis>(
      `${this.base}/analysis/${encodeURIComponent(symbol)}?resolution=${resolution}`,
    );
  }

  opportunities(symbols: string, resolution = '60'): Observable<ScanResult> {
    return this.http.get<ScanResult>(
      `${this.base}/opportunities?symbols=${encodeURIComponent(symbols)}&resolution=${resolution}`,
    );
  }

  orderbook(symbol: string): Observable<unknown> {
    return this.http.get<unknown>(
      `${this.base}/market/orderbook/${encodeURIComponent(symbol)}`,
    );
  }

  placeOrder(request: OrderRequest): Observable<unknown> {
    return this.http.post<unknown>(`${this.base}/orders`, request);
  }

  openOrders(): Observable<unknown> {
    return this.http.get<unknown>(`${this.base}/orders`);
  }

  cancelOrder(orderId: number): Observable<unknown> {
    return this.http.post<unknown>(`${this.base}/orders/cancel`, { order_id: orderId });
  }
}
