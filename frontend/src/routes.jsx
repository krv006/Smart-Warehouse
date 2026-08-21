import { useLocation } from 'react-router-dom'
import ApprovalsPage from '../components/ApprovalsPage'
import BookingPage from '../components/BookingPage'
import ClientDetailPage from '../components/ClientDetailPage'
import ConfiguratorPage from '../components/ConfiguratorPage'
import KassaPage from '../components/KassaPage'
import SectionTabs from '../components/SectionTabs'
import { can, isAccessiblePage } from '../lib/permissions'
import { getGroupForPage } from '../lib/nav'
import { resources } from '../lib/resources'
import { parseAppPath, pathForPage, crumbFromPath } from '../routes'

/**
 * Main content router — maps URL to page components.
 * ResourcePage, Dashboard, Reports, Buyurtmalar remain in App.jsx for now;
 * this module centralises route-to-view wiring.
 */
export default function AppRoutes({
  session,
  notify,
  routeInfo: routeInfoProp,
  dashboard,
  dashboardLoading,
  dashboardFilters,
  onDashboardFiltersChange,
  onCreateBuyurtma,
  onNavigate,
  navigateToPath,
  resourceReloadKey,
  onDataChange,
  ResourcePage,
  Dashboard,
  ReportsPage,
  BuyurtmalarPage,
  Editor,
  clientEditFromDetail,
  setClientEditFromDetail,
  setResourceReloadKey,
  loadDashboard,
  location,
}) {
  const locationFromHook = useLocation()
  const currentLocation = location || locationFromHook
  const routeInfo = routeInfoProp || parseAppPath(currentLocation.pathname)
  const active = routeInfo.page || 'Bosh sahifa'
  const activeGroup = getGroupForPage(active)

  return (
    <>
      {routeInfo.kind === 'client-detail' && can(session, 'clients_view') && (
        <ClientDetailPage
          clientId={routeInfo.clientId}
          tab={routeInfo.tab}
          session={session}
          notify={notify}
          onNavigate={navigateToPath}
          onEditClient={(client) => setClientEditFromDetail(client)}
          onNewOrder={(client) => onCreateBuyurtma(client.id)}
          onNewSale={() => { navigateToPath(pathForPage('Sotuvlar')); notify('Yangi sotuv formasi ochiladi.', 'success') }}
        />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Bosh sahifa' && can(session, 'dashboard') && (
        <Dashboard
          data={dashboard}
          loading={dashboardLoading}
          period={dashboardFilters}
          onPeriodChange={onDashboardFiltersChange}
          onCreateBuyurtma={onCreateBuyurtma}
          onNavigate={onNavigate}
          session={session}
        />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Hisobotlar' && can(session, 'reports_view') && (
        <ReportsPage notify={notify} />
      )}
      {(routeInfo.kind === 'page' || routeInfo.kind === 'invoice-detail' || routeInfo.kind === 'invoice-new' || routeInfo.kind === 'invoice-edit') && active === 'Buyurtmalar' && can(session, 'einvoice_view') && (
        <BuyurtmalarPage
          notify={notify}
          session={session}
          routeMode={
            routeInfo.kind === 'invoice-new' ? 'new'
              : routeInfo.kind === 'invoice-edit' ? 'edit'
                : routeInfo.kind === 'invoice-detail' ? 'view'
                  : 'list'
          }
          invoiceId={routeInfo.invoiceId || null}
          prefillClientId={routeInfo.kind === 'invoice-new' ? (currentLocation.state?.clientId ?? null) : null}
        />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Kassa' && can(session, 'cash_view') && (
        <>
          {activeGroup && (
            <SectionTabs groupKey={activeGroup} active={active} onSelect={(page) => navigateToPath(pathForPage(page))} session={session} />
          )}
          <KassaPage notify={notify} session={session} reloadKey={resourceReloadKey} onDataChange={onDataChange} />
        </>
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Konfigurator' && can(session, 'configurator_view') && (
        <ConfiguratorPage notify={notify} session={session} reloadKey={resourceReloadKey} />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Bron' && can(session, 'booking_view') && (
        <BookingPage notify={notify} session={session} reloadKey={resourceReloadKey} />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Tasdiqlash' && can(session, 'approvals_view') && (
        <ApprovalsPage notify={notify} session={session} reloadKey={resourceReloadKey} />
      )}
      {routeInfo.kind !== 'client-detail' && active !== 'Bosh sahifa' && active !== 'Hisobotlar' && active !== 'Buyurtmalar' && active !== 'Kassa' && active !== 'Konfigurator' && active !== 'Bron' && active !== 'Tasdiqlash' && isAccessiblePage(session, active) && resources[active] && (
        <>
          {activeGroup && (
            <SectionTabs groupKey={activeGroup} active={active} onSelect={(page) => navigateToPath(pathForPage(page))} session={session} />
          )}
          <ResourcePage
            title={active}
            notify={notify}
            reloadKey={resourceReloadKey}
            session={session}
            onDataChange={onDataChange}
            onNavigate={onNavigate}
            navigateToPath={navigateToPath}
          />
        </>
      )}
      {clientEditFromDetail && (
        <Editor
          title="Mijozlar"
          item={clientEditFromDetail}
          path="/clients/"
          close={() => setClientEditFromDetail(null)}
          done={() => { setClientEditFromDetail(null); setResourceReloadKey((v) => v + 1) }}
          notify={notify}
          session={session}
        />
      )}
      <span className="sr-only" aria-hidden="true">{crumbFromPath(currentLocation.pathname)}</span>
    </>
  )
}
