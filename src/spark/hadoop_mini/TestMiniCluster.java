/*
 * Prueba dirigida de Hadoop YARN/HDFS reales — documentado en el reporte
 * técnico (Anexo B) y en Producto 7, Sección 11.
 *
 * ESTADO: este archivo NO compila tal cual con solo hadoop-client-minicluster
 * (27.1 MB, sí versionado en jars/). Le falta org.apache.hadoop.conf.Configuration
 * y otras clases base, que viven en hadoop-client-runtime — un segundo .jar
 * de 40-70 MB que excede el límite de subida de archivos de este entorno
 * (30 MB) y no se pudo obtener.
 *
 * Se deja este archivo como evidencia honesta del intento, no como código
 * funcional. Para completarlo: descargar hadoop-client-runtime (misma
 * versión, 3.1.1) desde Maven Central, partido en fragmentos <30MB si hace
 * falta, y agregarlo al classpath de compilación y ejecución.
 */
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.fs.FSDataOutputStream;
import org.apache.hadoop.fs.FSDataInputStream;
import org.apache.hadoop.hdfs.MiniDFSCluster;
import org.apache.hadoop.yarn.server.MiniYARNCluster;
import org.apache.hadoop.yarn.conf.YarnConfiguration;
import org.apache.hadoop.yarn.api.records.ApplicationId;
import org.apache.hadoop.yarn.client.api.YarnClient;

import java.io.IOException;

public class TestMiniCluster {
    public static void main(String[] args) throws Exception {
        System.out.println("=== Iniciando MiniDFSCluster (HDFS real) ===");
        Configuration conf = new Configuration();
        conf.set("hadoop.tmp.dir", "/tmp/hadoop_minicluster");

        MiniDFSCluster.Builder builder = new MiniDFSCluster.Builder(conf);
        MiniDFSCluster hdfsCluster = builder.numDataNodes(2).build();
        hdfsCluster.waitActive();

        FileSystem fs = hdfsCluster.getFileSystem();
        System.out.println("HDFS NameNode URI real: " + fs.getUri());
        System.out.println("DataNodes activos: " + hdfsCluster.getDataNodes().size());

        // Escribir y leer un archivo REAL en HDFS
        Path archivo = new Path("/cgr/prueba_hdfs.txt");
        FSDataOutputStream out = fs.create(archivo);
        out.writeUTF("Contrato de prueba - Proyecto Interno 1.8.2 - CGR - HDFS real funcionando");
        out.close();

        FSDataInputStream in = fs.open(archivo);
        String contenido = in.readUTF();
        in.close();
        System.out.println("Contenido leído desde HDFS: " + contenido);
        System.out.println("Archivo existe en HDFS: " + fs.exists(archivo));

        System.out.println("\n=== Iniciando MiniYARNCluster (YARN real) ===");
        YarnConfiguration yarnConf = new YarnConfiguration();
        MiniYARNCluster yarnCluster = new MiniYARNCluster("cgr-test-yarn", 2, 1, 1);
        yarnCluster.init(yarnConf);
        yarnCluster.start();

        YarnClient yarnClient = YarnClient.createYarnClient();
        yarnClient.init(yarnCluster.getConfig());
        yarnClient.start();

        System.out.println("YARN ResourceManager activo, nodos registrados: " +
                yarnClient.getNodeReports().size());
        System.out.println("Estado del clúster YARN: " + yarnClient.getYarnClusterMetrics().getNumNodeManagers() + " NodeManagers");

        System.out.println("\nHDFS + YARN REALES VERIFICADOS — no son carpetas simuladas.");

        yarnClient.stop();
        yarnCluster.stop();
        hdfsCluster.shutdown();
        System.exit(0);
    }
}
