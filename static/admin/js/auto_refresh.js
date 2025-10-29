// iot_project/static/admin/js/auto_refresh.js

(function() {
    // Tempo de atualização em milissegundos (ex: 30000 = 30 segundos)
    const refreshInterval = 30000; 
    
    const currentPath = window.location.pathname;
    
    // 1. Definir os caminhos que DEVEM disparar o refresh (Listagens e Dashboard)
    const pathsToListings = [
        '/admin/devices/telemetrydata/', // Lista de TelemetryData
        '/admin/devices/scheduledtask/', // Lista de ScheduledTask
        '/devices/dashboard/',           // Dashboard Web
        '/admin/devices/device/',        // Lista de Device (Importante para garantir o heartbeat lá também)
    ];

    // 2. Definir os caminhos que NÃO DEVEM disparar o refresh (Páginas de Form)
    const isAddPage = currentPath.endsWith('/add/');
    const isChangePage = currentPath.match(/\/\d+\/change\/$/); // Regex para /ID/change/
    
    // 3. Verificar se estamos em uma listagem OU no dashboard
    const isOnListingPage = pathsToListings.some(path => currentPath.startsWith(path));

    // O refresh final só acontece se estiver em uma listagem/dashboard E não for uma página de formulário (add/change)
    const shouldRefresh = isOnListingPage && !isAddPage && !isChangePage;

    if (shouldRefresh) {
        
        console.log(`Auto Refresh ativado: Recarregando a página a cada ${refreshInterval / 1000} segundos.`);
        
        // Função para recarregar a página
        function autoRefresh() {
            window.location.reload(); 
        }

        // Configura o intervalo de tempo para a atualização
        setInterval(autoRefresh, refreshInterval);
    } else {
        console.log("Auto Refresh Desativado. Motivo: Página de formulário ou caminho não listado.");
    }
})();