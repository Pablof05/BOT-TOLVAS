import { NextResponse } from 'next/server'

// Auth temporalmente deshabilitado
export function middleware(request) {
  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/login', '/register'],
}
