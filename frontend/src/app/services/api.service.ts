import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Analysis,
  AppSettings,
  CronPreview,
  Health,
  Market,
  OrderRequest,
  ScanResult,
  ScheduleRequest,
  ScheduledRun,
  ScheduledRunDetail,
  ScheduledTask,
  SettingsUpdate,
} from '../models';

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

  markets(): Observable<{ markets: Market[] }> {
    return this.http.get<{ markets: Market[] }>(`${this.base}/markets`);
  }

  schedules(): Observable<{ timezone: string; tasks: ScheduledTask[] }> {
    return this.http.get<{ timezone: string; tasks: ScheduledTask[] }>(
      `${this.base}/schedules`,
    );
  }

  createSchedule(body: ScheduleRequest): Observable<ScheduledTask> {
    return this.http.post<ScheduledTask>(`${this.base}/schedules`, body);
  }

  updateSchedule(id: string, body: Partial<ScheduleRequest>): Observable<ScheduledTask> {
    return this.http.patch<ScheduledTask>(`${this.base}/schedules/${id}`, body);
  }

  deleteSchedule(id: string): Observable<{ deleted: string }> {
    return this.http.delete<{ deleted: string }>(`${this.base}/schedules/${id}`);
  }

  runSchedule(id: string): Observable<{ task_id: string; started: boolean }> {
    return this.http.post<{ task_id: string; started: boolean }>(
      `${this.base}/schedules/${id}/run`,
      {},
    );
  }

  validateCron(cron: string): Observable<CronPreview> {
    return this.http.post<CronPreview>(`${this.base}/schedules/validate`, { cron });
  }

  runs(taskId?: string): Observable<{ runs: ScheduledRun[] }> {
    const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
    return this.http.get<{ runs: ScheduledRun[] }>(`${this.base}/runs${query}`);
  }

  runDetail(id: string): Observable<ScheduledRunDetail> {
    return this.http.get<ScheduledRunDetail>(`${this.base}/runs/${id}`);
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

  settings(): Observable<AppSettings> {
    return this.http.get<AppSettings>(`${this.base}/settings`);
  }

  updateSettings(body: SettingsUpdate): Observable<AppSettings> {
    return this.http.put<AppSettings>(`${this.base}/settings`, body);
  }

  testLlm(): Observable<{ ok: boolean; detail: string }> {
    return this.http.post<{ ok: boolean; detail: string }>(
      `${this.base}/settings/test/llm`,
      {},
    );
  }

  testNobitex(): Observable<{ ok: boolean; detail: string }> {
    return this.http.post<{ ok: boolean; detail: string }>(
      `${this.base}/settings/test/nobitex`,
      {},
    );
  }
}
