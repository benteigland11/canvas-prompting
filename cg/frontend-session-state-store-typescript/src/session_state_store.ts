export type SessionStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface SessionState<T> {
  session: T | null;
  status: SessionStatus;
  error: Error | null;
  isAuthenticated: boolean;
}

export type Listener = () => void;

export class SessionStateStore<T> {
  private _state: SessionState<T> = {
    session: null,
    status: 'idle',
    error: null,
    isAuthenticated: false,
  };
  private _listeners = new Set<Listener>();

  get state(): SessionState<T> {
    return this._state;
  }

  subscribe(listener: Listener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _notify() {
    for (const listener of this._listeners) {
      listener();
    }
  }

  private _setState(updates: Partial<SessionState<T>>) {
    this._state = { ...this._state, ...updates };
    this._notify();
  }

  setSession(session: T | null) {
    this._setState({ 
      session, 
      status: 'ready', 
      error: null,
      isAuthenticated: session !== null 
    });
  }

  setStatus(status: SessionStatus) {
    this._setState({ status });
  }

  setError(error: Error) {
    this._setState({ status: 'error', error });
  }

  reset() {
    this._setState({
      session: null,
      status: 'idle',
      error: null,
      isAuthenticated: false
    });
  }

  async runAsync(work: Promise<T>): Promise<T> {
    this.setStatus('loading');
    try {
      const result = await work;
      this.setSession(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      this.setError(error);
      throw error;
    }
  }
}
