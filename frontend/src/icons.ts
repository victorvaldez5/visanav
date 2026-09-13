export const icons = Object.fromEntries(
    Object.entries(
        import.meta.glob('./assets/icons/*.svg', { query: '?raw', import: 'default', eager: true }) as Record<string, string>
    ).map(([path, svg]) => [path.split('/').pop()!.replace('.svg', ''), svg])
)