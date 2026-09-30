export const env = {
  apiUrl: import.meta.env.VITE_API_URL ?? '/api/v1',
  devUserId:
    import.meta.env.VITE_DEV_USER_ID ?? '00000000-0000-0000-0000-000000000001',
}
