import java.awt.Font;
import java.awt.GraphicsEnvironment;
import java.nio.file.Path;
import java.util.Arrays;
import javax.imageio.ImageIO;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;

// Проверка результатов средствами JDK: дополнительные тестовые зависимости не нужны.
class VerifyRender {
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        require(Arrays.asList(GraphicsEnvironment.getLocalGraphicsEnvironment()
                .getAvailableFontFamilyNames()).contains("DejaVu Sans"), "Нет шрифта DejaVu Sans");
        require(new Font("DejaVu Sans", Font.PLAIN, 14).canDisplayUpTo("Согласующий — заявка") == -1,
                "Шрифт не поддерживает кириллицу");

        Document regulation = readSvg(output.resolve("regulation.svg"));
        String text = regulation.getDocumentElement().getTextContent();
        for (String label : new String[] {"Инициатор", "Согласующий", "Исполнитель",
                "Подать заявку", "Описание потребности", "Комплект документов",
                "Данные полные?", "Вернуть на доработку", "Инструкция"}) {
            require(text.contains(label), "В SVG отсутствует подпись: " + label);
        }
        boolean hasLink = false;
        var links = regulation.getElementsByTagName("a");
        for (int i = 0; i < links.getLength(); i++) {
            var link = (org.w3c.dom.Element) links.item(i);
            hasLink |= "https://example.org/regulation".equals(link.getAttribute("href"))
                    || "https://example.org/regulation".equals(link.getAttribute("xlink:href"));
        }
        require(hasLink, "В SVG отсутствует ссылка на инструкцию");

        Document graphviz = readSvg(output.resolve("graphviz.svg"));
        String graphvizText = graphviz.getDocumentElement().getTextContent();
        require(graphvizText.contains("Заявка") && graphvizText.contains("Результат"),
                "Не отрендерена проверочная диаграмма Graphviz");
        for (String name : new String[] {"regulation", "graphviz"}) {
            var png = ImageIO.read(output.resolve(name + ".png").toFile());
            require(png != null && png.getWidth() > 50 && png.getHeight() > 50,
                    "Некорректный PNG: " + name);
            System.out.printf("%s: SVG OK, PNG %d x %d%n", name, png.getWidth(), png.getHeight());
        }
        System.out.println("Кириллица, шрифт, подключённая процедура и SVG-ссылка: OK");
    }

    private static Document readSvg(Path path) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Document doc = factory.newDocumentBuilder().parse(path.toFile());
        require("svg".equals(doc.getDocumentElement().getTagName()), "Файл не является SVG: " + path);
        return doc;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }
}
