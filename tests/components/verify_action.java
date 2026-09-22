import java.nio.file.Path;
import java.util.HashSet;
import java.util.Set;
import javax.imageio.ImageIO;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

// Проверяем наблюдаемый результат компонента без дополнительных зависимостей.
class VerifyAction {
    public static void main(String[] args) throws Exception {
        Path output = Path.of(args[0]);
        Document minimal = read(output, "action_minimal");
        String minimalText = text(minimal);
        has(minimalText, "РТЕ-01", "Ответственный:", "Согласующий", "Результат:", "Решение принято");
        for (String omitted : new String[] {"Срок:", "Инструкция / чек-лист", "Подрегламент:"})
            require(!minimalText.contains(omitted), "Пустое поле осталось в минимальном действии: " + omitted);
        require(count(minimalText, "РТЕ-01") == 1, "Повторное include продублировало действие");
        require(minimal.getElementsByTagName("image").getLength() == 1, "Повторное include изменило марку");

        Document content = read(output, "action_content");
        String contentText = text(content);
        has(contentText, "РТЕ-02", "РТЕ-03", "сущностей трекера", "Шаблон заключения",
                "Заключение по шаблону", "1. Проверить \"цель\"; сохранить замечания;",
                "2. Сверить комплект документов.", "3. Проверить каждую затронутую сущность",
                "Инструкция / чек-лист", "Подрегламент: проверка заявки");
        require(count(contentText, "Ответственный:") == 2, "Пунктуация изменила число действий");
        require(count(contentText, "Срок:") == 1, "Не скрыт незаданный срок второго действия");
        require(!contentText.contains("\\n"), "Вместо перевода строки выведен буквальный \\n");
        require(links(content).equals(Set.of("materials/review_template.html", "review_regulation.svg")),
                "Изменились ссылки внутри действия");
        Document preview = read(output, "action_content_preview");
        require(text(preview).equals(contentText) && links(preview).equals(links(content)),
                "Режим предпросмотра VS Code изменил содержимое или ссылки");

        String flow = text(read(output, "action_flow"));
        has(flow, "Автор", "Проверяющий", "Нужна доработка?", "Уведомить участников");
        for (int i = 1; i <= 5; i++)
            require(count(flow, "РПР-0" + i) == 1, "Пропущен или повторён идентификатор РПР-0" + i);
        has(flow, "РПР-04 Уведомить участников Ответственный: Проверяющий Результат: Участники уведомлены о новой редакции",
                "РПР-05 Завершить работу");
        require(count(flow, "Ответственный:") == 5 && count(flow, "Результат:") == 5,
                "Каждое из пяти действий должно содержать ответственного и результат");

        Document main = read(output, "basic_regulation");
        for (String name : new String[] {"basic_regulation", "basic_regulation_no_lanes"}) {
            String mainText = text(read(output, name));
            has(mainText, "Согласование заявки", "Инициатор", "Согласующий", "В заключении есть замечания?",
                    "Подготовить или доработать заявку", "При повторном проходе исправить замечания.",
                    "РСЗ-03 Согласовать заявку", "РСЗ-04 Получить решение");
            for (int i = 1; i <= 4; i++)
                // После ID действия идёт пробел; ссылка на него в основании имеет вид «РСЗ-02:».
                require(count(mainText, "РСЗ-0" + i + " ") == 1, "Пропущен или повторён ID действия в " + name);
            require(count(mainText, "Ответственный:") == 4 && count(mainText, "Результат:") == 4,
                    "Ожидались четыре действия в " + name);
        }
        require(links(main).equals(Set.of("materials/review_template.html", "review_regulation.svg")),
                "Основной пример потерял ссылки");
        require(links(read(output, "review_regulation")).equals(
                Set.of("materials/review_template.html", "basic_regulation.svg")),
                "Дочерний регламент потерял шаблон или обратную ссылку");
        has(text(read(output, "portable")), "РПЕ-01", "Перенос библиотеки", "Подключение работает");

        for (String name : new String[] {"action_minimal", "action_content", "action_flow",
                "basic_regulation", "basic_regulation_no_lanes", "review_regulation", "portable", "action_content_preview"}) {
            Document doc = read(output, name);
            require(doc.getElementsByTagName("image").getLength() == 1, "Ожидался один знак в " + name);
            Element mark = (Element) doc.getElementsByTagName("image").item(0);
            require(href(mark).startsWith("data:image/png;base64,"), "Знак зависит от внешнего файла: " + name);
            var png = ImageIO.read(output.resolve(name + ".png").toFile());
            require(png != null && png.getWidth() > 50 && png.getHeight() > 50, "Некорректный PNG: " + name);
            System.out.printf("%s: SVG OK, PNG %d × %d%n", name, png.getWidth(), png.getHeight());
        }
        System.out.println("Параметры, переносы, пунктуация, пропуск полей, ссылки и переносимость: OK");
    }

    private static Document read(Path output, String name) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Document doc = factory.newDocumentBuilder().parse(output.resolve(name + ".svg").toFile());
        require("svg".equals(doc.getDocumentElement().getTagName()), "Ожидался SVG: " + name);
        return doc;
    }

    private static String text(Document doc) {
        StringBuilder result = new StringBuilder();
        var nodes = doc.getElementsByTagName("text");
        for (int i = 0; i < nodes.getLength(); i++) result.append(nodes.item(i).getTextContent()).append(' ');
        return result.toString().replaceAll("(?U)\\s+", " ").trim();
    }

    private static String href(Element element) {
        return element.hasAttribute("href") ? element.getAttribute("href") : element.getAttribute("xlink:href");
    }

    private static Set<String> links(Document doc) {
        Set<String> result = new HashSet<>();
        var nodes = doc.getElementsByTagName("a");
        for (int i = 0; i < nodes.getLength(); i++) result.add(href((Element) nodes.item(i)));
        return result;
    }

    private static int count(String text, String fragment) {
        return (text.length() - text.replace(fragment, "").length()) / fragment.length();
    }

    private static void has(String text, String... fragments) {
        for (String fragment : fragments) require(text.contains(fragment), "Нет текста: " + fragment);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }
}
