import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, throwError } from 'rxjs';
import { catchError, map, switchMap, tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

interface ApiErrorBody {
  error?: string;
  use_staff_portal?: boolean;
  staff_login_url?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private csrfToken = '';

  private url(path: string): string {
    const base = environment.apiBaseUrl.replace(/\/$/, '');
    return `${base}${path.startsWith('/') ? path : `/${path}`}`;
  }

    private bootstrapCsrf(): Observable<void> {
    return this.http.get<{ csrfToken: string }>(this.url('/csrf/'), { withCredentials: true }).pipe(
      tap((res) => {
        this.csrfToken = res.csrfToken;
      }),
      map(() => undefined),
    );
  }

  private jsonHeaders(): HttpHeaders {
    return new HttpHeaders({
      'Content-Type': 'application/json',
      ...(this.csrfToken ? { 'X-CSRFToken': this.csrfToken } : {}),
    });
  }

  get<T>(path: string): Observable<T> {
    return this.http.get<T>(this.url(path), { withCredentials: true }).pipe(catchError((err) => this.fail(err)));
  }

  postJson<T>(path: string, body: unknown): Observable<T> {
    return this.bootstrapCsrf().pipe(
      switchMap(() =>
        this.http.post<T>(this.url(path), body, {
          withCredentials: true,
          headers: this.jsonHeaders(),
        }),
      ),
      catchError((err) => this.fail(err)),
    );
  }

  putJson<T>(path: string, body: unknown): Observable<T> {
    return this.bootstrapCsrf().pipe(
      switchMap(() =>
        this.http.put<T>(this.url(path), body, {
          withCredentials: true,
          headers: this.jsonHeaders(),
        }),
      ),
      catchError((err) => this.fail(err)),
    );
  }

  postForm<T>(path: string, body: FormData): Observable<T> {
    const headers = this.csrfToken ? new HttpHeaders({ 'X-CSRFToken': this.csrfToken }) : undefined;
    return this.bootstrapCsrf().pipe(
      switchMap(() =>
        this.http.post<T>(this.url(path), body, {
          withCredentials: true,
          headers,
        }),
      ),
      catchError((err) => this.fail(err)),
    );
  }

  private fail(err: HttpErrorResponse): Observable<never> {
    const body = (err.error || {}) as ApiErrorBody;
    const message = body.error || err.message || 'Request failed.';
    const error = new Error(message) as Error & {
      useStaffPortal?: boolean;
      staffLoginUrl?: string;
    };
    if (body.use_staff_portal) {
      error.useStaffPortal = true;
      error.staffLoginUrl = body.staff_login_url || environment.staffLoginUrl;
    }
    return throwError(() => error);
  }
}
