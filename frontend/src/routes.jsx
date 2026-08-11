import { useLocation } from 'react-router-dom'
import ClientDetailPage from '../components/ClientDetailPage'
import SectionTabs from '../components/SectionTabs'
import { can, isAccessiblePage } from '../lib/permissions'
import { getGroupForPage } from '../lib/nav'
import { resources } from '../lib/resources'
import { parseAppPath, pathForPage, crumbFromPath } from '../routes'

/**
 * Main content router — maps URL to page components.
 * ResourcePage, Dashboard, Reports, EInvoice remain in App.jsx for now;
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
  onCreateOrder,
  onNavigate,
  navigateToPath,
  resourceReloadKey,
  onDataChange,
  ResourcePage,
  Dashboard,
  ReportsPage,
  EInvoicePage,
  Editor,
  OrderEditor,
  clientEditFromDetail,
  setClientEditFromDetail,
  setResourceReloadKey,
  orderModalOpen,
  setOrderModalOpen,
  orderPrefillClient,
  setOrderPrefillClient,
  loadDashboard,
}) {
  const location = useLocation()
  const routeInfo = routeInfoProp || parseAppPath(location.pathname)
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
          onNewOrder={(client) => onCreateOrder(client.id)}
          onNewSale={() => { navigateToPath(pathForPage('Sotuvlar')); notify('Yangi sotuv formasi ochiladi.', 'success') }}
        />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Bosh sahifa' && can(session, 'dashboard') && (
        <Dashboard
          data={dashboard}
          loading={dashboardLoading}
          period={dashboardFilters}
          onPeriodChange={onDashboardFiltersChange}
          onCreateOrder={onCreateOrder}
          onNavigate={onNavigate}
          session={session}
        />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Hisobotlar' && can(session, 'reports_view') && (
        <ReportsPage notify={notify} />
      )}
      {routeInfo.kind !== 'client-detail' && active === 'Elektron faktura' && can(session, 'einvoice_view') && (
        <EInvoicePage notify={notify} session={session} />
      )}
      {routeInfo.kind !== 'client-detail' && active !== 'Bosh sahifa' && active !== 'Hisobotlar' && active !== 'Elektron faktura' && isAccessiblePage(session, active) && resources[active] && (
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
            initialOrderHistoryId={routeInfo.kind === 'order-detail' ? routeInfo.orderId : null}
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
      {orderModalOpen && can(session, 'orders_manage') && (
        <OrderEditor
          close={() => { setOrderModalOpen(false); setOrderPrefillClient(null) }}
          done={() => {
            setOrderModalOpen(false)
            setOrderPrefillClient(null)
            setResourceReloadKey((value) => value + 1)
            loadDashboard(true)
          }}
          notify={notify}
          session={session}
          prefillClientId={orderPrefillClient}
        />
      )}
      <span className="sr-only" aria-hidden="true">{crumbFromPath(location.pathname)}</span>
    </>
  )
}
