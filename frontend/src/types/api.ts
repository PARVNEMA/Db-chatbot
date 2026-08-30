export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  error: ErrorDetail | null;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details: unknown | null;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface PaginationParams {
  skip?: number;
  limit?: number;
}
