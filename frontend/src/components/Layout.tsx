import { Link, NavLink, Outlet } from 'react-router'

import { cx } from '../lib/cx'
import styles from './Layout.module.css'

function navClass({ isActive }: { isActive: boolean }) {
  return cx(styles.navLink, isActive && styles.navActive)
}

export function Layout() {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.bar}>
          <Link to="/" className={styles.brand}>
            <span className={styles.mark} aria-hidden="true" />
            <span className={styles.brandName}>Keitaro</span>
            <span className={styles.brandSub}>обёртка</span>
          </Link>
          <nav className={styles.nav} aria-label="Разделы">
            <NavLink to="/" end className={navClass}>
              Кампании
            </NavLink>
            <NavLink to="/campaigns/new" className={navClass}>
              Новая<span className={styles.long}> кампания</span>
            </NavLink>
          </nav>
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
