import { Link, useLocation } from 'react-router-dom'

function DocumentIcon() {
  return <svg aria-hidden="true" className="h-[17px] w-[17px]" fill="none" viewBox="0 0 24 24"><path d="M6.5 3.5h8l3 3v14h-11z" stroke="currentColor" strokeWidth="1.7" /><path d="M14.5 3.5v4h3M9 12h6M9 16h4" stroke="currentColor" strokeWidth="1.7" /></svg>
}

function StyleIcon() {
  return <svg aria-hidden="true" className="h-[17px] w-[17px]" fill="none" viewBox="0 0 24 24"><path d="M5 5.5h14M5 10.5h14M5 15.5h9" stroke="currentColor" strokeWidth="1.7" /><path d="M18 15v5M15.5 17.5h5" stroke="currentColor" strokeWidth="1.7" /></svg>
}

export function WorkspaceSidebar() {
  const location = useLocation()
  const stylesActive = location.pathname.startsWith('/styles')

  return (
    <aside className="flex min-h-screen w-[224px] shrink-0 flex-col border-r border-app-border bg-app-shell px-3.5 py-6 max-[720px]:min-h-0 max-[720px]:w-full max-[720px]:border-b max-[720px]:border-r-0 max-[720px]:px-3.5 max-[720px]:py-3">
      <p className="mb-3 ml-2.5 text-[10px] font-bold uppercase tracking-[0.1em] text-[#9a928b] max-[720px]:hidden">Разделы</p>
      <nav className="grid gap-1 max-[720px]:flex max-[720px]:gap-1.5" aria-label="Основная навигация">
        <Link className={`flex w-full items-center gap-2.5 rounded-control px-2.5 py-2.5 text-sm no-underline transition-colors max-[720px]:w-auto max-[720px]:py-2 ${!stylesActive ? 'bg-white font-semibold text-app-text shadow-[0_1px_2px_rgb(23_23_23_/_6%)]' : 'text-app-muted hover:bg-[#e9e4df] hover:text-app-text'}`} to="/">
          <span className={!stylesActive ? 'text-app-accent' : ''}><DocumentIcon /></span><span>Документы</span>
        </Link>
        <Link className={`flex w-full items-center gap-2.5 rounded-control px-2.5 py-2.5 text-sm no-underline transition-colors max-[720px]:w-auto max-[720px]:py-2 ${stylesActive ? 'bg-white font-semibold text-app-text shadow-[0_1px_2px_rgb(23_23_23_/_6%)]' : 'text-app-muted hover:bg-[#e9e4df] hover:text-app-text'}`} to="/styles">
          <span className={stylesActive ? 'text-app-accent' : ''}><StyleIcon /></span><span>Стили</span>
        </Link>
      </nav>
      <div className="flex-1 max-[720px]:hidden" />
    </aside>
  )
}
